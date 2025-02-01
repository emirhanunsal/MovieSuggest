import boto3
import os
from datetime import datetime

# DynamoDB connection
dynamodb = boto3.resource(
    'dynamodb',
    region_name=os.getenv("AWS_DEFAULT_REGION"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)

# Tables
user_table = dynamodb.Table('Users')
request_table = dynamodb.Table('PartnerRequests')
preferences_table = dynamodb.Table('UserPreferences')
partners_table = dynamodb.Table('Partners')  # New table for partner relationships


def create_user(user):
    # Add a new user to the Users table
    item = {
        "UserID": user["UserID"],
        "email": user["email"],
        "password": user["password"],
    }
    user_table.put_item(Item=item)
    return item


def get_user(user_id):
    # Retrieve user information from the Users table
    try:
        response = user_table.get_item(Key={"UserID": user_id})
        print(f"get_user response: {response}")
        return response.get("Item")
    except Exception as e:
        print(f"Error in get_user: {e}")
        return None


def send_partner_request(sender_id, receiver_id):
    # Send a partner request from one user to another
    try:
        partners_table = dynamodb.Table('Partners')

        # Check if the sender already has a partner
        sender_partners = partners_table.scan(
            FilterExpression="UserID = :sender",
            ExpressionAttributeValues={":sender": sender_id}
        )
        if sender_partners["Count"] > 0:
            return {"error": "You already have a partner and cannot send more requests"}

        # Check if the receiver already has a partner
        receiver_partners = partners_table.scan(
            FilterExpression="UserID = :receiver",
            ExpressionAttributeValues={":receiver": receiver_id}
        )
        if receiver_partners["Count"] > 0:
            return {"error": "This user already has a partner and cannot receive requests"}

        # Check if the sender already has a pending request
        existing_request = request_table.scan(
            FilterExpression="SenderUserID = :sender",
            ExpressionAttributeValues={":sender": sender_id}
        )
        if existing_request["Count"] > 0:
            return {"error": "You can only send one partner request at a time"}

        # Check if the receiver already has a pending request
        receiver_pending_requests = request_table.scan(
            FilterExpression="ReceiverUserID = :receiver AND #s = :pending",
            ExpressionAttributeValues={
                ":receiver": receiver_id,
                ":pending": "pending"
            },
            ExpressionAttributeNames={"#s": "Status"}
        )
        if receiver_pending_requests["Count"] > 0:
            return {"error": "This user already has pending requests"}

        # Add the partner request to the PartnerRequests table
        request_table.put_item(Item={
            "ReceiverUserID": receiver_id,
            "SenderUserID": sender_id,
            "Status": "pending",
            "CreatedAt": datetime.utcnow().isoformat()
        })
        return {"message": "Partner request sent successfully"}
    except Exception as e:
        print(f"Error in send_partner_request: {e}")
        return {"error": str(e)}


# Retrieve partner requests
def get_partner_requests(user_id):
    try:
        # Get incoming requests for the user
        received_requests = request_table.query(
            KeyConditionExpression="ReceiverUserID = :user_id",
            ExpressionAttributeValues={":user_id": user_id}
        )

        # Get outgoing requests from the user
        sent_requests = request_table.scan(
            FilterExpression="SenderUserID = :user_id",
            ExpressionAttributeValues={":user_id": user_id}
        )

        return {
            "received_requests": received_requests["Items"],
            "sent_requests": sent_requests["Items"]
        }
    except Exception as e:
        print(f"Error in get_partner_requests: {e}")
        return {"received_requests": [], "sent_requests": []}


def accept_partner_request(sender_id, receiver_id):
    # Accept a partner request
    try:
        # Check if the partner request exists
        response = request_table.scan(
            FilterExpression="ReceiverUserID = :receiver AND SenderUserID = :sender",
            ExpressionAttributeValues={
                ":receiver": receiver_id,
                ":sender": sender_id
            }
        )
        if "Items" not in response or len(response["Items"]) == 0:
            return {"error": "Partner request not found"}

        # Update the partner request status to 'accepted'
        request_table.update_item(
            Key={"ReceiverUserID": receiver_id},
            UpdateExpression="SET #s = :accepted",
            ExpressionAttributeValues={":accepted": "accepted"},
            ExpressionAttributeNames={"#s": "Status"}
        )

        # Create a partner relationship
        create_partner_relationship(receiver_id, sender_id)

        return {"message": "Partner request accepted and relationship created successfully"}
    except Exception as e:
        print(f"Error in accept_partner_request: {e}")
        return {"error": str(e)}


def create_partner_relationship(user_id, partner_id):
    # Create a partner relationship between two users
    try:
        partners_table.put_item(Item={
            "UserID": user_id,
            "PartnerID": partner_id,
            "Status": "active",
            "CreatedAt": datetime.utcnow().isoformat()
        })
        partners_table.put_item(Item={
            "UserID": partner_id,
            "PartnerID": user_id,
            "Status": "active",
            "CreatedAt": datetime.utcnow().isoformat()
        })
        return {"message": "Partner relationship created successfully"}
    except Exception as e:
        print(f"Error in create_partner_relationship: {e}")
        return {"error": str(e)}


def reject_partner_request(sender_id, receiver_id):
    try:
        # Check if the partner request exists
        response = request_table.scan(
            FilterExpression="ReceiverUserID = :receiver AND SenderUserID = :sender",
            ExpressionAttributeValues={
                ":receiver": receiver_id,
                ":sender": sender_id
            }
        )
        if "Items" not in response or len(response["Items"]) == 0:
            return {"error": "Partner request not found"}

        # Update the request status to 'rejected'
        request_table.update_item(
            Key={"ReceiverUserID": receiver_id},
            UpdateExpression="SET #s = :rejected",
            ExpressionAttributeValues={":rejected": "rejected"},
            ExpressionAttributeNames={"#s": "Status"}
        )

        return {"message": "Partner request rejected successfully"}
    except Exception as e:
        print(f"Error in reject_partner_request: {e}")
        return {"error": str(e)}
