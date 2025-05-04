# Spotify Circle API

A FastAPI backend that allows users to connect their Spotify accounts and compare their music preferences with others.

## Features

- Spotify OAuth authentication
- Get user's top tracks and artists
- Connect with other users
- Compare music preferences with connected users

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
- `GET /top-artists?user_id={id}`: Get user's top artists
- `POST /connect/{user_id}/{connected_user_id}`: Connect two users
- `GET /compare/{user_id}/{connected_user_id}`: Compare two users' music preferences

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