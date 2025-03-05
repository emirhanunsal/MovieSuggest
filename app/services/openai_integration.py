import openai
import os
import boto3
import time
import re
from app.services.crud import get_user_preferences
from datetime import datetime

# OpenAI API Key
openai.api_key = os.getenv("OPENAI_API_KEY")

# DynamoDB Connection
dynamodb = boto3.resource(
    'dynamodb',
    region_name=os.getenv("AWS_DEFAULT_REGION"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)
movies_table = dynamodb.Table('Movies')  # Movies table

def call_openai_with_retry(func, retries=5, delay=2):
    """
    Retry mechanism for OpenAI API calls until a valid response is returned.
    """
    for attempt in range(retries):
        try:
            result = func()
            if "choices" in result and len(result["choices"]) > 0:
                return result
            else:
                print(f"Invalid response format on attempt {attempt + 1}. Retrying...")
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
        time.sleep(delay)
    raise ValueError("Failed to get a valid response from OpenAI API after retries.")

def call_openai_with_prompt(prompt: str, model: str = "gpt-4", max_tokens: int = 300, temperature: float = 0.7) -> dict:
    """
    Generic function to call OpenAI API with a specific prompt.
    """
    try:
        def openai_call():
            return openai.ChatCompletion.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a movie assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature
            )

        response = call_openai_with_retry(openai_call)

        if response is None:
            raise ValueError("❌ OpenAI API response is None. Possible issue with API key or connection.")

        print(f"✅ OpenAI API Response: {response}")

        return response
    except Exception as e:
        print(f"🚨 OpenAI API Call Failed: {e}")
        return {"error": str(e)}

def parse_openai_response(response):
    """
    Parse the OpenAI API response to extract genre and description safely.
    """
    try:
        content = response['choices'][0]['message']['content'].strip()

        match = re.search(r"Genre:\s*(.+)\s*Description:\s*(.+)", content, re.DOTALL)
        if not match:
            raise ValueError(f"Unexpected response format: {content}")

        genre = match.group(1).strip()
        description = match.group(2).strip()

        return genre, description
    except Exception as e:
        print(f"🚨 Error while parsing OpenAI response: {e}")
        raise ValueError("Error while parsing OpenAI response.") from e

def generate_details(movie_name: str) -> dict:
    """
    Check the database for movie details. If not found, generate them using OpenAI API and save to DB.
    """
    try:
        print(f"Checking database for movie: {movie_name}")
        # Önce database'de kontrol et
        response = movies_table.get_item(
            Key={"MovieName": movie_name}
        )
        
        if "Item" in response:
            print(f"Movie '{movie_name}' found in database")
            movie_data = response["Item"]
            # Genre'yi liste olarak al
            genres = movie_data.get("Genre", [])
            if isinstance(genres, set):
                genres = list(genres)
            return {
                "description": movie_data.get("Description", ""),
                "genre": genres
            }

        print(f"Movie '{movie_name}' not found in database, generating details...")
        # Detayları generate et
        prompt = (
            f"Generate a detailed but spoiler-free description (2-3 sentences) and genre for the movie '{movie_name}'. "
            f"Provide the output in this format: 'Genre: [genre1/genre2/genre3], Description: [description]'."
        )

        response = call_openai_with_prompt(prompt, max_tokens=800)
        if "error" in response:
            print(f"Error generating details for {movie_name}: {response['error']}")
            return {"error": "Film detayları alınamadı"}

        content = response['choices'][0]['message']['content'].strip()
        genre, description = parse_openai_response(response)

        # Genre'ları liste olarak sakla
        genres = [g.strip() for g in genre.split('/')]

        # Database'e kaydet
        movie_item = {
            "MovieName": movie_name,
            "Description": description,
            "Genre": genres  # Liste olarak kaydet
        }
        movies_table.put_item(Item=movie_item)
        print(f"Successfully generated and saved details for '{movie_name}'")

        return {
            "description": description,
            "genre": genres
        }
    except Exception as e:
        print(f"🚨 Error in generate_details for {movie_name}: {e}")
        return {"error": "Film detayları alınamadı"}

def generate_movie_recommendations(user_id: str, partner_id: str, existing_recommendations: list = None) -> list:
    """
    Generate movie recommendations based on two users' preferences from the database.
    Returns a list of movie dictionaries with titles and genres.
    """
    try:
        # Get preferences from database
        user_preferences = get_user_preferences(user_id)
        partner_preferences = get_user_preferences(partner_id)

        if "error" in user_preferences or "error" in partner_preferences:
            raise ValueError("Kullanıcı tercihleri bulunamadı")

        # Partners tablosundan daha önce önerilen tüm filmleri al
        partners_table = dynamodb.Table('Partners')
        previously_recommended = set()
        
        # Tüm önceki önerileri al
        response = partners_table.scan()
        for item in response.get("Items", []):
            if "Movies" in item:
                previously_recommended.update(item["Movies"])

        print(f"Previously recommended movies: {previously_recommended}")

        # Kullanıcı tercihlerini birleştir
        all_genres = set()
        all_movies = set()

        # Add user preferences
        if "Genre" in user_preferences:
            all_genres.update(user_preferences["Genre"])
        if "Movies" in user_preferences:
            all_movies.update(user_preferences["Movies"])

        # Add partner preferences
        if "Genre" in partner_preferences:
            all_genres.update(partner_preferences["Genre"])
        if "Movies" in partner_preferences:
            all_movies.update(partner_preferences["Movies"])

        if not all_genres and not all_movies:
            raise ValueError("Film tercihi bulunamadı")

        # Prepare OpenAI API prompt
        prompt = (
            f"Based on these users' combined preferences, suggest 5 NEW movies that they might enjoy.\n\n"
            f"Preferred genres: {', '.join(all_genres)}\n"
            f"Previously liked movies: {', '.join(all_movies)}\n"
            f"NEVER RECOMMEND these previously suggested movies: {', '.join(previously_recommended)}\n\n"
            "The response should be in this exact format for each movie (one per line):\n"
            "1. Movie Name: [name], Genre: [genre1/genre2/genre3]\n"
            "2. ... (repeat for 5 movies)\n\n"
            "IMPORTANT: You must suggest completely new movies that have never been recommended before. DO NOT suggest any movie from the 'NEVER RECOMMEND' list."
        )

        # Call OpenAI API with limited retries
        max_retries = 5
        for attempt in range(max_retries):
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[
                        {
                            "role": "system", 
                            "content": "You are a movie recommendation assistant. You must NEVER recommend any movies that were previously suggested. Always suggest completely new movies."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=300,
                    temperature=0.7
                )
                
                if response and "choices" in response and len(response["choices"]) > 0:
                    recommendations_text = response['choices'][0]['message']['content']
                    
                    # Parse the recommendations into a list of dictionaries
                    recommendations = []
                    for line in recommendations_text.strip().split('\n'):
                        if not line.strip():
                            continue
                            
                        try:
                            # Remove the number prefix
                            line = line.split('. ', 1)[1] if '. ' in line else line
                            
                            # Split into parts
                            parts = line.split(', ')
                            movie_name = parts[0].replace('Movie Name: ', '').strip()
                            
                            # Kesinlikle daha önce önerilmiş filmleri atlayalım
                            if movie_name in previously_recommended:
                                print(f"Skipping previously recommended movie: {movie_name}")
                                continue
                                
                            genres = parts[1].replace('Genre: ', '').strip().split('/')
                            genres = [g.strip() for g in genres]
                            
                            recommendations.append({
                                'title': movie_name,
                                'genres': genres
                            })
                        except Exception as parse_error:
                            print(f"Error parsing movie line: {parse_error}")
                            continue
                    
                    if recommendations:
                        return recommendations
                
                print(f"Attempt {attempt + 1} failed: Invalid response format")
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {str(e)}")
            
            if attempt < max_retries - 1:  # Don't sleep on the last attempt
                time.sleep(2)  # Wait 2 seconds before retrying
        
        return []
    except Exception as e:
        print(f"Error in generate_movie_recommendations: {e}")
        return []

async def generate_movie_details_async(movie_title: str, genres: list, movies_table):
    """
    Generate movie details asynchronously and save to database
    """
    try:
        # Önce database'de kontrol et
        response = movies_table.get_item(
            Key={"MovieName": movie_title}
        )
        
        if "Item" in response:
            print(f"Movie details already exist for {movie_title}")
            return
            
        # Detayları generate et
        details = generate_details(movie_title)
        if "error" in details:
            print(f"Error generating details for {movie_title}: {details['error']}")
            return
            
        # Genre'yi liste olarak kaydet
        if isinstance(genres, set):
            genres = list(genres)
            
        # Database'e kaydet
        movies_table.put_item(Item={
            "MovieName": movie_title,
            "Description": details.get("description", ""),
            "Genre": genres  # Liste olarak kaydet
        })
        print(f"Successfully generated and saved details for {movie_title}")
    except Exception as e:
        print(f"Error in generate_movie_details_async for {movie_title}: {e}")
        return
