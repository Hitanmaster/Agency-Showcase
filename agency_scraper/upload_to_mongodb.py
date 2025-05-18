import json
from pymongo import MongoClient

# Step 1: Connect to your MongoDB Atlas Cluster
client = MongoClient("mongodb+srv://Himanshu:Himanshu#0987@cluster0.mbirvgi.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")

# Step 2: Select database and collection
db = client["agency_database"]           # Database name
collection = db["koto_projects"]        # Collection name

# Step 3: Load your JSON file
with open("koto_data.json", "r", encoding="utf-8") as f:
    projects = json.load(f)

# Step 4: Insert into MongoDB
if isinstance(projects, list):
    collection.insert_many(projects)  # Insert all projects
else:
    collection.insert_one(projects)   # Insert single project (if somehow JSON is a single object)

print(f"✅ Successfully uploaded {len(projects)} projects to MongoDB!")
