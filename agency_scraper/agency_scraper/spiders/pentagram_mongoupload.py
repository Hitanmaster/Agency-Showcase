import os
import json
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure

try:
    from pymongo import MongoClient
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False
    print("pymongo library not found. MongoDB upload will be disabled. To enable, run: pip install pymongo")


def upload_to_mongodb(data_list, mongo_uri, db_name, collection_name):
    if not PYMONGO_AVAILABLE:
        print("MongoDB upload skipped: pymongo library is not available.")
        return
    if not data_list:
        print("No data to upload to MongoDB.")
        return
    if not mongo_uri or mongo_uri == "YOUR_MONGODB_ATLAS_CONNECTION_STRING":
        print("MongoDB URI not configured. Skipping MongoDB upload.")
        return
    try:
        print(
            f"Attempting to connect to MongoDB: {mongo_uri.split('@')[-1] if '@' in mongo_uri else mongo_uri} ...")
        client = MongoClient(mongo_uri)
        client.admin.command('ismaster')
        print("Successfully connected to MongoDB.")
        db = client[db_name]
        collection = db[collection_name]
        print(
            f"Inserting {len(data_list)} documents into {db_name}.{collection_name}...")
        result = collection.insert_many(data_list)
        print(f"Successfully inserted {len(result.inserted_ids)} documents.")
    except ConnectionFailure:
        print("MongoDB connection failed. Please check your URI, IP whitelisting, and network settings.")
    except OperationFailure as e:
        print(f"MongoDB operation failed: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during MongoDB upload: {e}")
    finally:
        if 'client' in locals() and hasattr(client, 'close'):
            client.close()
            print("MongoDB connection closed.")


def load_json_from_directory(directory_path):
    json_data_list = []
    for file_name in os.listdir(directory_path):
        if file_name.endswith(".json"):
            file_path = os.path.join(directory_path, file_name)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    json_data_list.extend(data)
                    print(f"Loaded {len(data)} items from {file_name}")
            except Exception as e:
                print(f"Failed to load {file_name}: {e}")
    return json_data_list


if __name__ == "__main__":
    # Set your MongoDB URI and other parameters
    MONGO_URI = "mongodb+srv://Himanshu:Himanshu#0987@cluster0.mbirvgi.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
    MONGO_DB_NAME = "agency_database"
    MONGO_COLLECTION_NAME = "pentagram_projects"  # Single collection to store all data

    # Directory containing the scraped JSON files
    json_directory = "scraped_pentagram_data"

    # Load all JSON data from the folder
    scraped_data = load_json_from_directory(json_directory)

    # If there is data to upload, send it to MongoDB
    if scraped_data:
        upload_to_mongodb(scraped_data, MONGO_URI, MONGO_DB_NAME, MONGO_COLLECTION_NAME)
    else:
        print("No data to upload to MongoDB.")

    print("\n--- Data upload completed. ---")
