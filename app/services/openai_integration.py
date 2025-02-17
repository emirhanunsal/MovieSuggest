import openai
import os
import boto3
import time
import re

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
            # Ensure the 'choices' list is valid and non-empty
            if "choices" in result and len(result["choices"]) > 0:
                return result
            else:
                print(f"Invalid response format on attempt {attempt + 1}. Retrying...")
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
        time.sleep(delay)
    raise ValueError("Failed to get a valid response from OpenAI API after retries.")

def parse_openai_response(response):
    """
    Parse the OpenAI API response to extract genre and description.
    """
    try:
        # Parse the response content
        result = response['choices'][0]['message']['content'].strip()

        # Validate and extract genre and description
        if "Genre:" not in result or "Description:" not in result:
            raise ValueError("The response format is invalid. Expected 'Genre:' and 'Description:' in the output.")

        genre = result.split("Genre:")[1].split(", Description:")[0].strip()
        description = result.split(", Description:")[1].strip()

        return genre, description
    except IndexError as e:
        raise ValueError("Unexpected response structure: 'choices' list is empty or malformed.") from e
    except Exception as e:
        raise ValueError("Error while parsing OpenAI response.") from e

import openai
import os
import boto3
import time
import re

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

def call_openai_with_prompt(prompt: str, model: str = "gpt-4o-mini", max_tokens: int = 300, temperature: float = 0.7) -> dict:
    """
    Generic function to call OpenAI API with a specific prompt.
    """
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

    return call_openai_with_retry(openai_call)

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
        # Check if movie already exists in the database
        response = movies_table.get_item(Key={"MovieName": movie_name})
        if "Item" in response:
            print("Movie found in the database.")
            return response["Item"]  # Return the movie details from DB

        # OpenAI çağrısı için prompt oluştur
        prompt = (
            f"Generate a brief description without spoiler and genre for a movie titled '{movie_name}'. "
            f"Provide the output in this format: 'Genre: [genre], Description: [description]'."
        )

        response = call_openai_with_prompt(prompt)
        genre, description = parse_openai_response(response)

        # Save to DynamoDB
        movie_item = {
            "MovieName": movie_name,
            "Genre": genre,
            "Description": description
        }
        movies_table.put_item(Item=movie_item)

        return movie_item  # Return the new movie details
    except Exception as e:
        print(f"🚨 Error in generate_details: {e}")
        return {"error": str(e)}





def generate_movie_recommendations(preferences: dict) -> str:
    """
    Generate movie recommendations based on user preferences.
    """
    try:
        genres = preferences.get("genres", [])
        movies = preferences.get("movies", [])

        if not genres and not movies:
            raise ValueError("No preferences provided for generating recommendations")

        # Prepare OpenAI API prompt
        prompt = (
            f"Based on the following preferences, suggest 5 movies with a brief, spoiler-free description:\n\n"
            f"Preferred genres: {', '.join(genres)}\n"
            f"Previously liked movies: {', '.join(movies)}\n\n"
            "The response should be in this format:\n"
            "1. Movie Name: [name], Genre: [genre], Description: [spoiler-free description]\n"
            "2. ... (repeat for 5 movies)\n"
        )

        # Call OpenAI API
        def openai_call():
            return openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a movie recommendation assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.7
            )

        response = call_openai_with_retry(openai_call)

        # Extract recommendations from the response
        recommendations = response['choices'][0]['message']['content']
        return recommendations
    except Exception as e:
        print(f"Error in generate_movie_recommendations: {e}")
        return "An error occurred while generating recommendations"


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

        # 🛠️ Genre ve Description'ı regex ile çekelim
        match = re.search(r"Genre:\s*(.+)\s*Description:\s*(.+)", content, re.DOTALL)
        if not match:
            raise ValueError(f"Unexpected response format: {content}")

        genre = match.group(1).strip()
        description = match.group(2).strip()

        return genre, description
    except Exception as e:
        print(f"🚨 Error while parsing OpenAI response: {e}")
        raise ValueError("Error while parsing OpenAI response.") from e
