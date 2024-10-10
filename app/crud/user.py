import random
import string
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.send_email import send_email_async
from app.models.otp import OTP
from app.models.user import User
from app.schemas.user import UserCreate, UserCreateResponse, UserUpdate
from app.core.security import hash_password, verify_password
from sqlalchemy.exc import SQLAlchemyError


def authenticate_user(db: Session, email: str, password: str):
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        return False
    return user


def get_user_by_email(db: Session, email: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database session is not available")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=404, detail=f"No user found with email: {email}"
        )
    return user


def get_user_by_id(db: Session, user_id: int):
    if db is None:
        raise HTTPException(status_code=500, detail="Database session is not available")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


async def create_user(db: Session, user: UserCreate):
    if db is None:
        raise HTTPException(status_code=500, detail="Database session is not available")
    
    # Check if the email already exists
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email is already registered")
    
    try:
        # Hash the user's password
        hashed_password = hash_password(user.password)

        # Create the new user object
        new_user = User(
            email=user.email,
            password=hashed_password,
            profile_image= "default.png",
            full_name=user.full_name,
            created_at=func.now(),
            updated_at=func.now()
        )

        # Add the new user to the database and commit
        db.add(new_user)
        db.commit()

        # Refresh the user instance to retrieve the auto-generated values like id
        db.refresh(new_user)
        
        # Prepare response by extracting fields from the new_user instance
        user_response = UserCreateResponse(
            user_id=new_user.user_id,
            email=new_user.email,
            full_name=new_user.full_name,
            created_at=new_user.created_at,
        )

        # Function to generate a 6-digit OTP
        otp_code_generate = ''.join(random.choices(string.digits, k=6))
        otp_data = {
            "user_id": new_user.user_id,
            "otps_code": otp_code_generate
        }
        create_otp(otp_data=otp_data, db=db)

        # send mail
        await send_email_async(new_user.email, {'title': 'OTP Register Code', 'name': new_user.full_name})

        return user_response

    except SQLAlchemyError as e:
        db.rollback()  # Rollback the transaction in case of failure
        raise HTTPException(
            status_code=500, detail=f"Database transaction failed: {str(e)}"
        )


def get_users(db: Session):
    if db is None:
        raise HTTPException(status_code=500, detail="Database session is not available")
    users = db.query(User).all()
    if not users:
        raise HTTPException(status_code=404, detail="No users found")
    return users


def update_user_by_id(db: Session, user_id: int, user_update: UserUpdate):
    if db is None:
        raise HTTPException(status_code=500, detail="Database session is not available")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user_update.full_name:
        user.full_name = user_update.full_name
    if user_update.profile_picture:
        user.profile_picture = user_update.profile_picture
    if user_update.username:
        user.username = user_update.username
    if user_update.password:
        user.hashed_password = hash_password(user_update.password)
    user.updated_at = func.now()

    try:
        db.commit()
        db.refresh(user)
        return user
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Database transaction failed: {str(e)}"
        )


def delete_user_by_id(db: Session, user_id: int):
    if db is None:
        raise HTTPException(status_code=500, detail="Database session is not available")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        deleted_user = user
        db.delete(user)
        db.commit()
        return deleted_user
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Database transaction failed: {str(e)}"
        )

def create_otp(otp_data: object, db: Session):
    # Create a new OTP entry with the necessary fields
    new_otp = OTP(
        otps_code=otp_data.otps_code,  # Use otp_code field from input
        user_id=otp_data.user_id       # Use user_id field from input
    )

    # Add and commit the new OTP to the database
    db.add(new_otp)
    db.commit()
    db.refresh(new_otp)

    return new_otp  