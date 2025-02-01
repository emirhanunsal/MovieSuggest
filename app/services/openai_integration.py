import openai
import os
import boto3
import time

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

        # If not in DB, generate details using OpenAI
        def openai_call():
            messages = [
                {"role": "system", "content": "You are a movie expert assistant."},
                {"role": "user", "content": f"Generate a brief description without spoiler and genre for a movie titled '{movie_name}'. Provide the output in this format: 'Genre: [genre], Description: [description]'."}
            ]
            return openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=150,
                temperature=0.7
            )

        # Call OpenAI API with retry
        response = call_openai_with_retry(openai_call)

        # Parse the response
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
        print(f"Error in generate_details: {e}")
        return {"error": str(e)}
