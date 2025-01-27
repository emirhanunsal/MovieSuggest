import boto3
import os

dynamodb = boto3.resource(
    'dynamodb',
    region_name=os.getenv("AWS_DEFAULT_REGION"), 
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"), 
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY") 
)
table = dynamodb.Table('Users')

def create_user(user):
    item = {
        "UserID": user["UserID"],  
        "email": user["email"],
        "password": user["password"],
    }
    table.put_item(Item=item)
    return item

def get_user(user_id):
    try:
        response = table.get_item(Key={"UserID": user_id})
        print(f"get_user response: {response}")
        return response.get("Item")
    except Exception as e:
        print(f"Error in get_user: {e}")
        return None
