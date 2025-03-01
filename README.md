# 🎬 Movie Suggestion System for Couples

## 📌 Project Overview

This project provides AI-powered personalized movie recommendations for couples based on their favorite genres and previously watched movies. The system allows users to connect with their partners and receive tailored movie suggestions that reflect both individuals' preferences. The goal is to enhance shared viewing experiences by offering movies that cater to mutual interests.

The recommendation process leverages OpenAI’s language model to analyze user preferences and generate curated lists. Users can manage their preferences, update them over time, and refine recommendations. The system ensures that each suggested movie includes a genre classification and a short, spoiler-free description to help users make informed choices.

Additionally, the application provides a seamless experience through a simple authentication process, partner connection requests, and a well-defined API for managing user preferences and movie selections.

---

## 🚀 Technologies Used

**FastAPI, DynamoDB, OpenAI API (GPT-4), Docker**

---

## ⚙️ Installation & Setup

### 1️⃣ Set Up Environment Variables

Create a `.env` file and add the necessary credentials:

```env
OPENAI_API_KEY=your_openai_api_key
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_DEFAULT_REGION=your_aws_region
SECRET_KEY=your_secret_key
```

### 2️⃣ Run the Application Using Docker

```bash
docker compose up --build
```

---

## 📡 API Endpoints

### 🔹 User Management

- **Register a User**

  ```http
  POST /register
  ```

  **Body:**

  ```json
  {
    "UserID": "User123",
    "email": "user@example.com",
    "password": "mypassword"
  }
  ```

- **Login**

  ```http
  POST /login
  ```

  **Body:**

  ```json
  {
    "UserID": "User123",
    "password": "mypassword"
  }
  ```

### 🔹 Partner Requests

- **Send a Partner Request**

  ```http
  POST /send-partner-request/
  ```

  **Body:**

  ```json
  {
    "UserID": "User123",
    "PartnerID": "User456"
  }
  ```

- **View Partner Requests**

  ```http
  GET /get-partner-requests/{user_id}
  ```

- **Accept a Partner Request**

  ```http
  POST /accept-partner-request/
  ```

  **Body:**

  ```json
  {
    "SenderUserID": "User123",
    "ReceiverUserID": "User456"
  }
  ```

- **Reject a Partner Request**

  ```http
  POST /reject-partner-request/
  ```

  **Body:**

  ```json
  {
    "SenderUserID": "User123",
    "ReceiverUserID": "User456"
  }
  ```

### 🔹 Movie Preferences

- **Update Preferences**

  ```http
  PUT /preferences/{user_id}
  ```

  **Body:**

  ```json
  {
    "Genre": ["Action", "Sci-Fi"],
    "Movies": ["Inception"]
  }
  ```

- **Get Preferences**

  ```http
  GET /preferences/{user_id}
  ```

- **Add to Preferences**

  ```http
  PATCH /preferences/{user_id}/add
  ```

  **Body:**

  ```json
  {
    "Genre": ["Comedy"],
    "Movies": ["The Hangover"]
  }
  ```

- **Remove from Preferences**

  ```http
  PATCH /preferences/{user_id}/delete
  ```

  **Body:**

  ```json
  {
    "Genre": ["Horror"],
    "Movies": ["The Conjuring"]
  }
  ```

### 🔹 Movie Recommendations

- **Generate Movie Details**

  ```http
  GET /generate-details/?movie_name=Inception
  ```

- **Get Movie Recommendations**

  ```http
  GET /recommend-movies/?user_id=User123&partner_id=User456
  ```




