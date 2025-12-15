import uuid
import secrets

def generate_user_id():
    # Use secrets module to ensure cryptographically strong random numbers
    random_bytes = secrets.token_bytes(16)
    # Create a UUIDv4 from the random bytes
    new_uuid = uuid.UUID(bytes=random_bytes, version=4)
    print(f"Generated Secure User ID: {new_uuid}")
    return str(new_uuid)

if __name__ == "__main__":
    generate_user_id()
