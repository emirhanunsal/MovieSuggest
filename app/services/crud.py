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
        print(f"Attempting to get user with ID: {user_id}")
        
        # DynamoDB bağlantısını kontrol et
        print(f"AWS Region: {os.getenv('AWS_DEFAULT_REGION')}")
        print(f"AWS Access Key ID: {os.getenv('AWS_ACCESS_KEY_ID')}")
        print(f"AWS Secret Key exists: {'Yes' if os.getenv('AWS_SECRET_ACCESS_KEY') else 'No'}")
        
        # Tablo adını kontrol et
        print(f"Table name: {user_table.name}")
        
        # Scan ile kullanıcıyı bul
        scan_response = user_table.scan(
            FilterExpression="UserID = :user_id",
            ExpressionAttributeValues={":user_id": user_id}
        )
        print(f"Scan response: {scan_response}")
        
        if not scan_response.get("Items"):
            print(f"User not found: {user_id}")
            return None
            
        user_data = scan_response["Items"][0]
        print(f"Found user data: {user_data}")

        # Get partner information from Partners table using scan
        partners_response = partners_table.scan(
            FilterExpression="UserID = :user_id",
            ExpressionAttributeValues={":user_id": user_id}
        )
        
        print(f"Partners table response: {partners_response}")
        
        if partners_response.get("Items"):
            partner_data = partners_response["Items"][0]
            user_data["partner_id"] = partner_data["PartnerID"]
            print(f"Found partner data: {partner_data}")

        print(f"Final user data: {user_data}")
        return user_data
    except Exception as e:
        print(f"Error in get_user: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return None


def send_partner_request(sender_id, receiver_id):
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
            FilterExpression="SenderUserID = :sender AND #s = :pending",
            ExpressionAttributeValues={
                ":sender": sender_id,
                ":pending": "pending"
            },
            ExpressionAttributeNames={"#s": "Status"}
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
        current_time = datetime.utcnow().isoformat()
        request_table.put_item(Item={
            "ReceiverUserID": receiver_id,
            "SenderUserID": sender_id,
            "Status": "pending",
            "CreatedAt": current_time
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
        print(f"Getting partner requests for user: {user_id}")
        
        # Get incoming requests for the user using scan
        received_requests = request_table.scan(
            FilterExpression="ReceiverUserID = :user_id AND #s = :pending",
            ExpressionAttributeValues={
                ":user_id": user_id,
                ":pending": "pending"
            },
            ExpressionAttributeNames={"#s": "Status"}
        )

        # Get outgoing requests from the user using scan
        sent_requests = request_table.scan(
            FilterExpression="SenderUserID = :user_id AND #s = :pending",
            ExpressionAttributeValues={
                ":user_id": user_id,
                ":pending": "pending"
            },
            ExpressionAttributeNames={"#s": "Status"}
        )

        print(f"Received requests scan response: {received_requests}")
        print(f"Sent requests scan response: {sent_requests}")

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

        print(f"Mapped received requests: {mapped_received}")
        print(f"Mapped sent requests: {mapped_sent}")

        return {
            "received_requests": mapped_received,
            "sent_requests": mapped_sent
        }
    except Exception as e:
        print(f"Error in get_partner_requests: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
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
        timestamp = datetime.utcnow().isoformat()
        print(f"Adding notification for user {user_id} at {timestamp}")
        
        item = {
            "UserID": user_id,
            "Timestamp": timestamp,
            "Message": message,
            "Type": notification_type,
            "IsRead": False
        }
        print(f"Notification item to be added: {item}")
        
        notifications_table.put_item(Item=item)
        return {"message": "Bildirim başarıyla eklendi"}
    except Exception as e:
        print(f"Error in add_notification: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return {"error": str(e)}

def get_notifications(user_id: str):
    """
    Kullanıcının bildirimlerini getirir.
    """
    try:
        print(f"Getting notifications for user: {user_id}")
        
        response = notifications_table.scan(
            FilterExpression="UserID = :user_id",
            ExpressionAttributeValues={":user_id": user_id}
        )
        print(f"Scan response: {response}")
        
        # En yeni bildirimleri önce göstermek için sıralama
        notifications = sorted(
            response.get("Items", []),
            key=lambda x: x.get("Timestamp", ""),
            reverse=True
        )
        
        print(f"Sorted notifications: {notifications}")
        return notifications
    except Exception as e:
        print(f"Error in get_notifications: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return []

def mark_notification_as_read(user_id: str, timestamp: str):
    """
    Bildirimi okundu olarak işaretler.
    """
    try:
        print(f"Marking notification as read for user {user_id} at timestamp {timestamp}")
        
        # Önce bildirimi bul
        response = notifications_table.scan(
            FilterExpression="UserID = :user_id AND #ts = :timestamp",
            ExpressionAttributeValues={
                ":user_id": user_id,
                ":timestamp": timestamp
            },
            ExpressionAttributeNames={
                "#ts": "Timestamp"
            }
        )
        
        if not response.get("Items"):
            return {"error": "Bildirim bulunamadı"}
            
        # Bildirimi güncelle
        notification = response["Items"][0]
        notifications_table.put_item(
            Item={
                "UserID": user_id,
                "Timestamp": timestamp,
                "Message": notification["Message"],
                "Type": notification["Type"],
                "IsRead": True
            }
        )
        print("Notification marked as read successfully")
        return {"message": "Bildirim okundu olarak işaretlendi"}
    except Exception as e:
        print(f"Error in mark_notification_as_read: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return {"error": str(e)}

def get_unread_notification_count(user_id: str) -> int:
    """
    Kullanıcının okunmamış bildirim sayısını döndürür.
    """
    try:
        response = notifications_table.scan(
            FilterExpression="UserID = :user_id AND IsRead = :is_read",
            ExpressionAttributeValues={
                ":user_id": user_id,
                ":is_read": False
            }
        )
        return len(response.get("Items", []))
    except Exception as e:
        print(f"Error in get_unread_notification_count: {str(e)}")
        return 0

def delete_partner(user_id):
    try:
        print(f"Attempting to delete partner relationship for user: {user_id}")
        
        # Get partner information using scan
        response = partners_table.scan(
            FilterExpression="UserID = :user_id",
            ExpressionAttributeValues={
                ":user_id": user_id
            }
        )
        
        print(f"Partners table scan response: {response}")
        
        if not response["Items"]:
            return {"error": "Partner ilişkisi bulunamadı"}

        user_partner = response["Items"][0]
        partner_id = user_partner["PartnerID"]
        print(f"Found partner_id: {partner_id}")

        try:
            # Delete from Partners table for both users
            print(f"Deleting from Partners table for user: {user_id}")
            partners_table.delete_item(
                Key={
                    "UserID": user_id
                }
            )
            
            print(f"Deleting from Partners table for partner: {partner_id}")
            partners_table.delete_item(
                Key={
                    "UserID": partner_id
                }
            )
        except Exception as e:
            print(f"Error deleting from Partners table: {e}")
            raise e

        try:
            # Delete from PartnerRequests table
            print("Deleting from PartnerRequests table")
            
            # İlgili tüm partner isteklerini bul
            requests_as_receiver = request_table.scan(
                FilterExpression="ReceiverUserID = :user_id",
                ExpressionAttributeValues={
                    ":user_id": user_id
                }
            )
            
            requests_as_receiver_partner = request_table.scan(
                FilterExpression="ReceiverUserID = :partner_id",
                ExpressionAttributeValues={
                    ":partner_id": partner_id
                }
            )
            
            print(f"Found requests where user is receiver: {requests_as_receiver}")
            print(f"Found requests where partner is receiver: {requests_as_receiver_partner}")
            
            # Kullanıcının alıcı olduğu istekleri sil
            for request in requests_as_receiver.get("Items", []):
                print(f"Deleting request where user is receiver: {request}")
                request_table.delete_item(
                    Key={
                        "ReceiverUserID": user_id
                    }
                )
            
            # Partnerin alıcı olduğu istekleri sil
            for request in requests_as_receiver_partner.get("Items", []):
                print(f"Deleting request where partner is receiver: {request}")
                request_table.delete_item(
                    Key={
                        "ReceiverUserID": partner_id
                    }
                )
            
        except Exception as e:
            print(f"Error deleting from PartnerRequests table: {e}")
            raise e

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
        print(f"Error in delete_partner: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return {"error": str(e)}

def withdraw_partner_request(sender_id, receiver_id):
    try:
        # İsteğin var olup olmadığını kontrol et
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
            return {"error": "Geri çekilecek partner isteği bulunamadı"}

        # İsteği sil
        request_table.delete_item(
            Key={"ReceiverUserID": receiver_id}
        )

        # Alıcıya bildirim gönder
        add_notification(
            receiver_id,
            f"{sender_id} partner isteğini geri çekti.",
            "request_withdrawn"
        )

        return {"message": "Partner isteği başarıyla geri çekildi"}
    except Exception as e:
        print(f"Error in withdraw_partner_request: {e}")
        return {"error": str(e)}

