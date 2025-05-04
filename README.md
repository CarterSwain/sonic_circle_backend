🎧 Sonic Circle — Backend API
Sonic Circle is a FastAPI-powered backend that connects Spotify users, visualizes musical overlap, and helps discover friends with similar tastes.

## Features

- Spotify OAuth 2.0 login with Spotipy
- Store & manage Spotify users and their access tokens securely
- Retrieve top tracks and artists
- Mutual “Link” system like a friendship model
- Compare music taste between any two linked users (including profile images, top track, and artist artwork)
- Search users by Spotify ID or email
- Suggest connections with strangers based on shared music preferences
- Full profile endpoint for displaying top artist, top track, and Spotify profile info

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up your environment variables in `.env`:
- Get your Spotify API credentials from [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
- Set up a PostgreSQL database and update the DATABASE_URL
- Create a secret key for your application

4. Start the server:
```bash
uvicorn main:app --reload
```

## API Endpoints

- `GET /`: Welcome message
- `GET /login`: Redirects to Spotify login
- `GET /callback`: Handles Spotify OAuth callback
- `GET /top-tracks?user_id={id}`: Get user's top tracks
- `GET /top-artists?user_id={id}`: Fetches user's top artists with genres, popularity, and images.
- `GET /profile/{user_id}`: Returns a user's profile info including top track, top artist, and Spotify profile image.
- `GET /users/search?q={query}`: Search users by Spotify ID or email.
- `GET /suggested-links/{user_id}`: Suggests users with shared top artists for potential connection.
- `POST /connect/{user_id}/{connected_user_id}`: Connect two users
- `GET /linked-users/{user_id}`: Retrieves users that the current user is connected with.
- `GET /compare/{user_id}/{connected_user_id}`: Compares top tracks and artists between two users. 


## Database Schema

### Users Table
- id (Primary Key)
- spotify_id (Unique)
- access_token
- refresh_token

### Connections Table
- id (Primary Key)
- user_id (Foreign Key)
- connected_user_id (Foreign Key) 