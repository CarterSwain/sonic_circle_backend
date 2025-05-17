from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, or_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
import os
from dotenv import load_dotenv
import logging
import time

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize FastAPI app
app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database models
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=True)
    spotify_id = Column(String, unique=True, index=True)
    access_token = Column(String)
    expires_at = Column(Integer)
    refresh_token = Column(String)

    connections = relationship(
        "Connection",
        back_populates="user",
        foreign_keys="[Connection.user_id]"
    )

# Connection model
class Connection(Base):
    __tablename__ = "connections"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    connected_user_id = Column(Integer, ForeignKey("users.id"))

    user = relationship(
        "User",
        back_populates="connections",
        foreign_keys=[user_id]
    )

# Create tables
Base.metadata.create_all(bind=engine)

# Spotify OAuth setup
sp_oauth = SpotifyOAuth(
    client_id=os.getenv("SPOTIFY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
    scope="user-top-read user-read-private user-read-email"
)

# Dependency to get a database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Helper to refresh tokens
def get_spotify_client(user: User, db: Session):
    if user.expires_at and user.expires_at - int(time.time()) < 60:
        token_info = sp_oauth.refresh_access_token(user.refresh_token)
        user.access_token = token_info["access_token"]
        user.refresh_token = token_info["refresh_token"]
        user.expires_at = token_info["expires_at"]
        db.commit()
    return spotipy.Spotify(auth=user.access_token)

# Root endpoint
@app.get("/")
async def root():
    return {"message": "Welcome to Sonic Circle"}

# Login endpoint
@app.get("/login")
async def login():
    auth_url = sp_oauth.get_authorize_url()
    return RedirectResponse(auth_url)

# Logout endpoint
@app.post("/logout")
async def logout():
    return {"message": "Logout handled on frontend"}


# Callback endpoint
@app.get("/callback")
async def callback(code: str, db: Session = Depends(get_db)):
    try:
        token_info = sp_oauth.get_access_token(code)
        sp = spotipy.Spotify(auth=token_info["access_token"])
        user_info = sp.current_user()
        user = db.query(User).filter(User.spotify_id == user_info["id"]).first()
        if not user:
            user = User(
                spotify_id=user_info["id"],
                access_token=token_info["access_token"],
                refresh_token=token_info["refresh_token"],
                expires_at=token_info["expires_at"],
                email=user_info.get("email")
            )
            db.add(user)
        else:
            user.access_token = token_info["access_token"]
            user.refresh_token = token_info["refresh_token"]
            user.expires_at = token_info["expires_at"]
        db.commit()
        return {"message": "Successfully authenticated", "user_id": user.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Get top tracks
@app.get("/top-tracks")
async def get_top_tracks(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    sp = get_spotify_client(user, db)
    top_tracks_raw = sp.current_user_top_tracks(limit=50, time_range="medium_term")
    return {
        "tracks": [
            {
                "name": track["name"],
                "artist": track["artists"][0]["name"],
                "album": track["album"]["name"],
                "spotify_url": track["external_urls"]["spotify"],
                "album_image": track["album"]["images"][0]["url"]
            }
            for track in top_tracks_raw["items"]
        ]
    }

# Get top artists
@app.get("/top-artists")
async def get_top_artists(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    sp = get_spotify_client(user, db)
    top_artists_raw = sp.current_user_top_artists(limit=50, time_range="medium_term")
    return {
        "artists": [
            {
                "name": artist["name"],
                "genres": artist.get("genres", []),
                "popularity": artist["popularity"],
                "spotify_url": artist["external_urls"]["spotify"],
                "image": artist["images"][0]["url"] if artist["images"] else None
            }
            for artist in top_artists_raw["items"]
        ]
    }

# Search users
@app.get("/users/search")
async def search_users(
    q: str,
    limit: int = 10,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    users = db.query(User).filter(
        or_(
            User.spotify_id.ilike(f"%{q}%"),
            User.email.ilike(f"%{q}%")
        )
    ).offset(offset).limit(limit).all()

    return [
        {"id": u.id, "spotify_id": u.spotify_id, "email": u.email}
        for u in users
    ]

# Suggest connections
@app.get("/suggested-links/{user_id}")
async def suggest_links(user_id: int, db: Session = Depends(get_db)):
    current_user = db.query(User).filter(User.id == user_id).first()
    if not current_user:
        raise HTTPException(status_code=404, detail="User not found")
    sp_current = get_spotify_client(current_user, db)
    current_artist_ids = {
        artist["id"] for artist in sp_current.current_user_top_artists(limit=50)["items"]
    }
    suggestions = []
    for user in db.query(User).filter(User.id != user_id).all():
        try:
            sp = get_spotify_client(user, db)
            artists = sp.current_user_top_artists(limit=50)["items"]
            overlap = len(current_artist_ids & {a["id"] for a in artists})
            if overlap > 0:
                suggestions.append({
                    "id": user.id,
                    "spotify_id": user.spotify_id,
                    "shared_artist_count": overlap
                })
        except Exception as e:
            logging.warning(f"Error fetching data for user {user.id}: {e}")
            continue
    suggestions.sort(key=lambda s: s["shared_artist_count"], reverse=True)
    return suggestions

# Get linked users (Users that the current user is connected with)
@app.get("/linked-users/{user_id}")
async def get_linked_users(user_id: int, db: Session = Depends(get_db)):
    connections = db.query(Connection).filter(Connection.user_id == user_id).all()
    linked_user_ids = [conn.connected_user_id for conn in connections]
    linked_users = db.query(User).filter(User.id.in_(linked_user_ids)).all()
    return [
        {"id": user.id, "spotify_id": user.spotify_id, "email": user.email}
        for user in linked_users
    ]

# User profile endpoint
@app.get("/profile/{user_id}")
async def user_profile(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    sp = get_spotify_client(user, db)
    top_artist = sp.current_user_top_artists(limit=1)["items"][0]
    top_track = sp.current_user_top_tracks(limit=1)["items"][0]
    return {
        "id": user.id,
        "spotify_id": user.spotify_id,
        "top_artist": {
            "name": top_artist["name"],
            "image": top_artist["images"][0]["url"] if top_artist["images"] else None,
            "spotify_url": top_artist["external_urls"]["spotify"]
        },
        "top_track": {
            "name": top_track["name"],
            "artist": top_track["artists"][0]["name"],
            "album_image": top_track["album"]["images"][0]["url"],
            "spotify_url": top_track["external_urls"]["spotify"]
        }
    }

# Compare users endpoint
@app.get("/compare/{user_id}/{connected_user_id}")
async def compare_users(user_id: int, connected_user_id: int, db: Session = Depends(get_db)):
    user1 = db.query(User).filter(User.id == user_id).first()
    user2 = db.query(User).filter(User.id == connected_user_id).first()
    if not user1 or not user2:
        raise HTTPException(status_code=404, detail="One or both users not found")
    sp1 = get_spotify_client(user1, db)
    sp2 = get_spotify_client(user2, db)

    profile1 = sp1.current_user()
    profile2 = sp2.current_user()

    top_artist1 = sp1.current_user_top_artists(limit=1)["items"][0]
    top_artist2 = sp2.current_user_top_artists(limit=1)["items"][0]
    top_track1 = sp1.current_user_top_tracks(limit=1)["items"][0]
    top_track2 = sp2.current_user_top_tracks(limit=1)["items"][0]

    user1_tracks = {t["id"]: t for t in sp1.current_user_top_tracks(limit=50)["items"]}
    user2_track_ids = {t["id"] for t in sp2.current_user_top_tracks(limit=50)["items"]}
    shared_track_ids = user1_tracks.keys() & user2_track_ids

    common_tracks = [{
        "name": t["name"],
        "artist": t["artists"][0]["name"],
        "spotify_url": t["external_urls"]["spotify"],
        "album_image": t["album"]["images"][0]["url"] if t["album"]["images"] else None
    } for tid, t in user1_tracks.items() if tid in shared_track_ids]

    user1_artists = {a["id"]: a for a in sp1.current_user_top_artists(limit=50)["items"]}
    user2_artist_ids = {a["id"] for a in sp2.current_user_top_artists(limit=50)["items"]}
    shared_artist_ids = user1_artists.keys() & user2_artist_ids

    common_artists = [{
        "name": a["name"],
        "spotify_url": a["external_urls"]["spotify"],
        "image": a["images"][0]["url"] if a["images"] else None
    } for aid, a in user1_artists.items() if aid in shared_artist_ids]

    return {
        "user1": {
            "display_name": profile1.get("display_name"),
            "profile_image": profile1["images"][0]["url"] if profile1.get("images") else None,
            "spotify_url": profile1["external_urls"]["spotify"],
            "top_track": {
                "name": top_track1["name"],
                "artist": top_track1["artists"][0]["name"],
                "album_image": top_track1["album"]["images"][0]["url"],
                "spotify_url": top_track1["external_urls"]["spotify"]
            },
            "top_artist": {
                "name": top_artist1["name"],
                "image": top_artist1["images"][0]["url"] if top_artist1.get("images") else None,
                "spotify_url": top_artist1["external_urls"]["spotify"]
            }
        },
        "user2": {
            "display_name": profile2.get("display_name"),
            "profile_image": profile2["images"][0]["url"] if profile2.get("images") else None,
            "spotify_url": profile2["external_urls"]["spotify"],
            "top_track": {
                "name": top_track2["name"],
                "artist": top_track2["artists"][0]["name"],
                "album_image": top_track2["album"]["images"][0]["url"],
                "spotify_url": top_track2["external_urls"]["spotify"]
            },
            "top_artist": {
                "name": top_artist2["name"],
                "image": top_artist2["images"][0]["url"] if top_artist2.get("images") else None,
                "spotify_url": top_artist2["external_urls"]["spotify"]
            }
        },
        "shared_track_count": len(common_tracks),
        "shared_artist_count": len(common_artists),
        "shared_tracks": common_tracks,
        "shared_artists": common_artists
    }
