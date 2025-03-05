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
partners_table = dynamodb.Table('Partners')
notifications_table = dynamodb.Table('Notifications')  # Yeni tablo


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
        # Get user data using scan
        response = user_table.scan(
            FilterExpression="UserID = :user_id",
            ExpressionAttributeValues={":user_id": user_id}
        )
        
        if not response["Items"]:
            return None
            
        user_data = response["Items"][0]

        # Get partner information from Partners table using scan
        partners_response = partners_table.scan(
            FilterExpression="UserID = :user_id",
            ExpressionAttributeValues={":user_id": user_id}
        )
        
        if partners_response.get("Items"):
            partner_data = partners_response["Items"][0]
            user_data["partner_id"] = partner_data["PartnerID"]

        print(f"get_user response: {user_data}")
        return user_data
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

        # Alıcıya bildirim gönder
        add_notification(
            receiver_id,
            f"{sender_id} size partner isteği gönderdi.",
            "partner_request"
        )

        return {"message": "Partner request sent successfully"}
    except Exception as e:
        print(f"Error in send_partner_request: {e}")
        return {"error": str(e)}


# Retrieve partner requests
def get_partner_requests(user_id):
    try:
        # Get incoming requests for the user using scan
        received_requests = request_table.scan(
            FilterExpression="ReceiverUserID = :user_id",
            ExpressionAttributeValues={":user_id": user_id}
        )

        # Get outgoing requests from the user using scan
        sent_requests = request_table.scan(
            FilterExpression="SenderUserID = :user_id",
            ExpressionAttributeValues={":user_id": user_id}
        )

        # Map field names for received requests
        mapped_received = []
        for item in received_requests.get("Items", []):
            mapped_received.append({
                "SenderUserID": item.get("SenderUserID"),
                "Timestamp": item.get("CreatedAt"),
                "Status": item.get("Status")
            })

        # Map field names for sent requests
        mapped_sent = []
        for item in sent_requests.get("Items", []):
            mapped_sent.append({
                "ReceiverUserID": item.get("ReceiverUserID"),
                "Timestamp": item.get("CreatedAt"),
                "Status": item.get("Status")
            })

        print(f"Received requests: {mapped_received}")
        print(f"Sent requests: {mapped_sent}")

        return {
            "received_requests": mapped_received,
            "sent_requests": mapped_sent
        }
    except Exception as e:
        print(f"Error in get_partner_requests: {e}")
        return {"received_requests": [], "sent_requests": []}


def accept_partner_request(sender_id, receiver_id):
    try:
        # Check if the partner request exists using scan with filter
        response = request_table.scan(
            FilterExpression="ReceiverUserID = :receiver AND SenderUserID = :sender AND #s = :pending",
            ExpressionAttributeValues={
                ":receiver": receiver_id,
                ":sender": sender_id,
                ":pending": "pending"
            },
            ExpressionAttributeNames={"#s": "Status"}
        )
        
        if not response["Items"]:
            return {"error": "Partner isteği bulunamadı"}

        # Update the partner request status to 'accepted'
        request_table.update_item(
            Key={"ReceiverUserID": receiver_id},
            UpdateExpression="SET #s = :accepted",
            ExpressionAttributeValues={
                ":accepted": "accepted"
            },
            ExpressionAttributeNames={"#s": "Status"}
        )

        # Create a partner relationship
        create_partner_relationship(receiver_id, sender_id)

        # Gönderene bildirim gönder
        add_notification(
            sender_id,
            f"{receiver_id} partner isteğinizi kabul etti.",
            "request_accepted"
        )

        return {"message": "Partner isteği kabul edildi ve ilişki başarıyla oluşturuldu"}
    except Exception as e:
        print(f"Error in accept_partner_request: {e}")
        return {"error": str(e)}


def create_partner_relationship(user_id, partner_id):
    # Create a partner relationship between two users
    try:
        # Create entries in Partners table
        current_time = datetime.utcnow().isoformat()
        
        partners_table.put_item(Item={
            "UserID": user_id,
            "PartnerID": partner_id,
            "Status": "active",
            "CreatedAt": current_time
        })
        partners_table.put_item(Item={
            "UserID": partner_id,
            "PartnerID": user_id,
            "Status": "active",
            "CreatedAt": current_time
        })

        return {"message": "Partner ilişkisi başarıyla oluşturuldu"}
    except Exception as e:
        print(f"Error in create_partner_relationship: {e}")
        return {"error": str(e)}


def reject_partner_request(sender_id, receiver_id):
    try:
        # Check if the partner request exists using scan with filter
        response = request_table.scan(
            FilterExpression="ReceiverUserID = :receiver AND SenderUserID = :sender AND #s = :pending",
            ExpressionAttributeValues={
                ":receiver": receiver_id,
                ":sender": sender_id,
                ":pending": "pending"
            },
            ExpressionAttributeNames={"#s": "Status"}
        )
        
        if not response["Items"]:
            return {"error": "Partner isteği bulunamadı"}

        # Update the request status to 'rejected'
        request_table.update_item(
            Key={"ReceiverUserID": receiver_id},
            UpdateExpression="SET #s = :rejected",
            ExpressionAttributeValues={
                ":rejected": "rejected"
            },
            ExpressionAttributeNames={"#s": "Status"}
        )

        # Gönderene bildirim gönder
        add_notification(
            sender_id,
            f"{receiver_id} partner isteğinizi reddetti.",
            "request_rejected"
        )

        return {"message": "Partner isteği başarıyla reddedildi"}
    except Exception as e:
        print(f"Error in reject_partner_request: {e}")
        return {"error": str(e)}


def get_user_preferences(user_id):
    try:
        # Get user preferences using scan
        response = preferences_table.scan(
            FilterExpression="UserID = :user_id",
            ExpressionAttributeValues={":user_id": user_id}
        )
        
        if not response["Items"]:
            return {"error": "Preferences not found for the given UserID"}
        
        # Convert set items to strings
        item = response["Items"][0]  # Get the first (and should be only) item
        if "Genre" in item:
            item["Genre"] = [str(genre) for genre in item["Genre"]]
        if "Movies" in item:
            item["Movies"] = [str(movie) for movie in item["Movies"]]
            
        return item
    except Exception as e:
        print(f"Error in get_user_preferences: {e}")
        return {"error": str(e)}
    
def update_user_preferences(user_id, genre=None, movies=None):
    try:
        update_expression = []
        expression_attribute_values = {}

        # Update genre if provided
        if genre:
            update_expression.append("Genre = :genre")
            expression_attribute_values[":genre"] = set(genre)  # Convert to set for DynamoDB SS type

        # Update movies if provided
        if movies:
            update_expression.append("Movies = :movies")
            expression_attribute_values[":movies"] = set(movies)  # Convert to set for DynamoDB SS type

        if not update_expression:
            return {"error": "No updates provided"}

        # Build the update expression
        update_expression = "SET " + ", ".join(update_expression)

        # Update the item in the UserPreferences table
        preferences_table.update_item(
            Key={"UserID": user_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values
        )

        return {"message": "Preferences updated successfully"}
    except Exception as e:
        print(f"Error in update_user_preferences: {e}")
        return {"error": str(e)}

def add_to_user_preferences(user_id, genre=None, movies=None):
    try:
        update_expression = []
        expression_attribute_values = {}

        # Add new genres to the existing Genre set
        if genre:
            update_expression.append("ADD Genre :genre")
            expression_attribute_values[":genre"] = set(genre)  # Convert to set for DynamoDB SS type

        # Add new movies to the existing Movies set
        if movies:
            update_expression.append("ADD Movies :movies")
            expression_attribute_values[":movies"] = set(movies)  # Convert to set for DynamoDB SS type

        if not update_expression:
            return {"error": "No updates provided"}

        # Build the update expression
        update_expression = " ".join(update_expression)

        # Update the item in the UserPreferences table
        preferences_table.update_item(
            Key={"UserID": user_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values
        )

        return {"message": "Preferences updated successfully (added new items)"}
    except Exception as e:
        print(f"Error in add_to_user_preferences: {e}")
        return {"error": str(e)}

def delete_from_user_preferences(user_id, genre=None, movies=None):
    try:
        update_expression = []
        expression_attribute_values = {}

        # Remove specified genres from the Genre set
        if genre:
            update_expression.append("DELETE Genre :genre")
            expression_attribute_values[":genre"] = set(genre)  # Convert to set for DynamoDB SS type

        # Remove specified movies from the Movies set
        if movies:
            update_expression.append("DELETE Movies :movies")
            expression_attribute_values[":movies"] = set(movies)  # Convert to set for DynamoDB SS type

        if not update_expression:
            return {"error": "No items provided to delete"}

        # Build the update expression
        update_expression = " ".join(update_expression)

        # Update the item in the UserPreferences table
        preferences_table.update_item(
            Key={"UserID": user_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values
        )

        return {"message": "Preferences updated successfully (deleted items)"}
    except Exception as e:
        print(f"Error in delete_from_user_preferences: {e}")
        return {"error": str(e)}


def get_combined_preferences(user_id: str, partner_id: str) -> dict:
    """
    Combine the preferences of two matched users.
    """
    try:
        # Retrieve preferences of both users
        user_preferences = get_user_preferences(user_id)
        partner_preferences = get_user_preferences(partner_id)

        if "error" in user_preferences or "error" in partner_preferences:
            return {}

        # Set birleşimi için | operatörü kullanılır
        combined_genres = list(set(user_preferences.get("Genre", [])) | set(partner_preferences.get("Genre", [])))
        combined_movies = list(set(user_preferences.get("Movies", [])) | set(partner_preferences.get("Movies", [])))

        return {
            "genres": combined_genres,
            "movies": combined_movies
        }
    except Exception as e:
        print(f"Error in get_combined_preferences: {e}")
        return {}


def add_notification(user_id: str, message: str, notification_type: str):
    """
    Kullanıcıya bildirim ekler.
    """
    try:
        notifications_table.put_item(Item={
            "UserID": user_id,
            "Timestamp": datetime.utcnow().isoformat(),
            "Message": message,
            "Type": notification_type,
            "IsRead": False
        })
        return {"message": "Bildirim başarıyla eklendi"}
    except Exception as e:
        print(f"Error in add_notification: {e}")
        return {"error": str(e)}

def get_notifications(user_id: str):
    """
    Kullanıcının bildirimlerini getirir.
    """
    try:
        response = notifications_table.scan(
            FilterExpression="UserID = :user_id",
            ExpressionAttributeValues={":user_id": user_id}
        )
        
        # En yeni bildirimleri önce göstermek için sıralama
        notifications = sorted(
            response.get("Items", []),
            key=lambda x: x.get("Timestamp", ""),
            reverse=True
        )
        
        return notifications
    except Exception as e:
        print(f"Error in get_notifications: {e}")
        return []

def mark_notification_as_read(user_id: str, timestamp: str):
    """
    Bildirimi okundu olarak işaretler.
    """
    try:
        # Find notification using scan
        response = notifications_table.scan(
            FilterExpression="UserID = :user_id AND #ts = :timestamp",
            ExpressionAttributeValues={
                ":user_id": user_id,
                ":timestamp": timestamp
            },
            ExpressionAttributeNames={"#ts": "Timestamp"}
        )
        
        if not response["Items"]:
            return {"error": "Bildirim bulunamadı"}
            
        # Update the notification
        notifications_table.update_item(
            Key={
                "UserID": user_id,
                "Timestamp": timestamp
            },
            UpdateExpression="SET IsRead = :read",
            ExpressionAttributeValues={":read": True}
        )
        return {"message": "Bildirim okundu olarak işaretlendi"}
    except Exception as e:
        print(f"Error in mark_notification_as_read: {e}")
        return {"error": str(e)}

def delete_partner(user_id):
    try:
        # Get partner information using scan
        response = partners_table.scan(
            FilterExpression="UserID = :user_id AND #s = :active",
            ExpressionAttributeValues={
                ":user_id": user_id,
                ":active": "active"
            },
            ExpressionAttributeNames={"#s": "Status"}
        )
        
        if not response["Items"]:
            return {"error": "Partner ilişkisi bulunamadı"}

        partner_id = response["Items"][0]["PartnerID"]

        # Delete from Partners table for both users
        partners_table.delete_item(Key={"UserID": user_id})
        partners_table.delete_item(Key={"UserID": partner_id})

        # Delete from PartnerRequests table
        # Önce kullanıcının gönderdiği istekleri sil
        sent_requests = request_table.scan(
            FilterExpression="SenderUserID = :user_id",
            ExpressionAttributeValues={":user_id": user_id}
        )
        for request in sent_requests.get("Items", []):
            request_table.delete_item(
                Key={"ReceiverUserID": request["ReceiverUserID"]}
            )

        # Sonra kullanıcının aldığı istekleri sil
        received_requests = request_table.query(
            KeyConditionExpression="ReceiverUserID = :user_id",
            ExpressionAttributeValues={":user_id": user_id}
        )
        for request in received_requests.get("Items", []):
            request_table.delete_item(
                Key={"ReceiverUserID": user_id}
            )

        # Delete from Movies table for both users
        movies_table = dynamodb.Table('Movies')
        movies_table.delete_item(Key={"UserID": user_id})
        movies_table.delete_item(Key={"UserID": partner_id})

        # Send notifications to both users
        add_notification(
            user_id,
            f"Partner ilişkiniz sonlandırıldı.",
            "partner_deleted"
        )
        add_notification(
            partner_id,
            f"{user_id} partner ilişkisini sonlandırdı.",
            "partner_deleted"
        )

        return {"message": "Partner ilişkisi başarıyla sonlandırıldı"}
    except Exception as e:
        print(f"Error in delete_partner: {e}")
        return {"error": str(e)}

