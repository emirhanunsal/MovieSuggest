import boto3
import os

dynamodb = boto3.resource(
    'dynamodb',
    region_name=os.getenv("AWS_DEFAULT_REGION"), 
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"), 
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY") 
)
table = dynamodb.Table('UserPreferences')

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
    
def send_partner_request(UserID, PartnerID):
    """
    Partner isteği gönderir.
    """
    try:
        response = table.scan(
            FilterExpression="(UserID = :UserID AND PartnerID = :PartnerID) OR (UserID = :PartnerID AND PartnerID = :UserID)",
            ExpressionAttributeValues={
                ":UserID": UserID,
                ":PartnerID": PartnerID
            }
        )
        if response.get("Items"):
            existing_status = response["Items"][0].get("Status")
            if existing_status in ["pending", "accepted"]:
                return {"error": "Partner request already exists with status: " + existing_status}

        table.update_item(
            Key={"UserID": UserID},
            UpdateExpression="SET PartnerID = :PartnerID, #s = :Status",
            ExpressionAttributeValues={
                ":PartnerID": PartnerID,
                ":Status": "pending"
            },
            ExpressionAttributeNames={
                "#s": "Status"  
            }
        )

        
        table.update_item(
            Key={"UserID": PartnerID},
            UpdateExpression="SET PartnerID = :UserID, #s = :Status",
            ExpressionAttributeValues={
                ":UserID": UserID,
                ":Status": "pending"
            },
            ExpressionAttributeNames={
                "#s": "Status"
            }
        )

        return {"message": "Partner request sent successfully"}
    except Exception as e:
        print(f"Error in send_partner_request: {e}")
        return {"error": str(e)}
