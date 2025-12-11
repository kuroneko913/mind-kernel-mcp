import boto3
import os
import shutil
import subprocess
import sys
import zipfile

def create_deployment_package(build_dir=".build_lambda", zip_path="lambda_function.zip"):
    print(f"Creating deployment package in {build_dir}...")
    
    # Clean previous build
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
    os.makedirs(build_dir)
    
    # 1. Install dependencies (requests is needed in Lambda)
    # Pydantic/MCP are NOT needed in Lambda for this simple logic, only requests and boto3 (boto3 is built-in but good to be sure)
    # We install to build_dir
    subprocess.check_call([
        sys.executable, "-m", "pip", "install", 
        "requests", "boto3", 
        "--target", build_dir,
        "--no-cache-dir"
    ])
    
    # 2. Copy application code
    # We need mind_kernel_mcp package in root
    pkg_dest = os.path.join(build_dir, "mind_kernel_mcp")
    shutil.copytree("mind_kernel_mcp", pkg_dest,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
    )
    
    # 3. Zip it
    print(f"Zipping to {zip_path}...")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(build_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, build_dir)
                zipf.write(file_path, arcname)
    
    print("Deployment package created.")
    return zip_path

def deploy_lambda():
    endpoint_url = os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566")
    region = os.getenv("AWS_REGION", "us-east-1")
    function_name = os.getenv("LAMBDA_FUNCTION_NAME", "MindKernelFunction")
    
    client = boto3.client(
        "lambda",
        endpoint_url=endpoint_url,
        region_name=region,
        aws_access_key_id="test",
        aws_secret_access_key="test"
    )
    
    zip_file = create_deployment_package()
    
    with open(zip_file, "rb") as f:
        zip_content = f.read()
    
    # Environment variables for Lambda
    env_vars = {
        "GITHUB_TOKEN": os.getenv("GITHUB_TOKEN", ""),
        "REPO_OWNER": os.getenv("REPO_OWNER", ""),
        "REPO_NAME": os.getenv("REPO_NAME", ""),
        "DYNAMODB_TABLE_NAME": os.getenv("DYNAMODB_TABLE_NAME", "UserSecrets"),
        # IMPORTANT: LocalStack Lambda needs to reach LocalStack
        # In Docker Compose, 'localstack' is the hostname
        "AWS_ENDPOINT_URL": os.getenv("AWS_ENDPOINT_URL_LAMBDA", "http://localstack:4566")
    }

    try:
        print(f"Deploying function {function_name} to {endpoint_url}...")
        
        try:
            client.get_function(FunctionName=function_name)
            print("Function exists. Updating code...")
            client.update_function_code(
                FunctionName=function_name,
                ZipFile=zip_content
            )
            # Update config (env vars)
            client.update_function_configuration(
                FunctionName=function_name,
                Environment={"Variables": env_vars}
            )
        except client.exceptions.ResourceNotFoundException:
            print("Function not found. Creating...")
            client.create_function(
                FunctionName=function_name,
                Runtime="python3.12",
                Role="arn:aws:iam::000000000000:role/lambda-role",
                Handler="mind_kernel_mcp.lambda_handler.lambda_handler",
                Code={"ZipFile": zip_content},
                Environment={"Variables": env_vars},
                Timeout=30,
                MemorySize=128
            )
            
        print("Deployment success!")
        
    except Exception as e:
        print(f"Deployment failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    deploy_lambda()
