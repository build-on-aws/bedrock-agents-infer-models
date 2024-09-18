import json
import os
import base64
import logging
import boto3
import io
import random
from PIL import Image
from botocore.exceptions import ClientError

# Initialize clients
s3 = boto3.client('s3')
sts_client = boto3.client('sts')
account_id = sts_client.get_caller_identity().get('Account')
region = boto3.Session().region_name
bedrock = boto3.client(service_name='bedrock-runtime', region_name=region)
sagemaker_runtime = boto3.client('sagemaker-runtime', region_name=region)

# Set up environment variables
bucket_name = f"bedrock-agent-images-{account_id}-{region}"
os.environ['S3_IMAGE_BUCKET'] = bucket_name
object_name = 'the_image.png'
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Define model IDs
TEXT_MODEL_IDS = [
    "amazon.titan-text-premier-v1:0",
    "amazon.titan-text-express-v1",
    "amazon.titan-text-lite-v1",
    "ai21.j2-ultra-v1",
    "ai21.j2-mid-v1",
    "anthropic.claude-3-sonnet-20240229-v1:0",
    "anthropic.claude-3-haiku-20240307-v1:0",
    "cohere.command-r-plus-v1:0",
    "cohere.command-r-v1:0",
    "meta.llama3-70b-instruct-v1:0",
    "meta.llama3-8b-instruct-v1:0",
    "mistral.mistral-large-2402-v1:0",
    "mistral.mixtral-8x7b-instruct-v0:1",
    "mistral.mistral-7b-instruct-v0:2",
    "mistral.mistral-small-2402-v1:0"
]

# Mapping for Bedrock and Stability AI Models
IMAGE_MODEL_IDS = {
    "Stable Diffusion": "stability.stable-diffusion-xl-v1",
    "Amazon Titan V1": "amazon.titan-image-generator-v1",
    "Amazon Titan V2": "amazon.titan-image-generator-v2:0",
    "Stable Diffusion Large V3": "stability.sd3-large-v1:0",
    "Stable Image Ultra": "stability.stable-image-ultra-v1:0",
    "Stable Image Core": "stability.stable-image-core-v1:0"
}

FALCON_MODEL_ENDPOINT = os.getenv('ENDPOINT')

def get_named_parameter(event, name):
    """Fetch a specific named parameter from event."""
    return next(item for item in event['parameters'] if item['name'] == name)['value']

def lambda_handler(event, context):
    print(event)
    
    # Determine the API path
    api_path = event.get('apiPath', '/unknown')
    
    if api_path == '/callBedrockModel':
        return call_model(event)
    elif api_path == '/callFalconModel':
        return call_falcon_model(event)
    else:
        return build_response(404, 'Invalid API path', event)

def call_model(event):
    """Handles requests for text/image models."""
    model_id = get_named_parameter(event, 'modelId')
    prompt = get_named_parameter(event, 'prompt')

    logger.info(f"MODEL ID: {model_id}")
    logger.info(f"PROMPT: {prompt}")

    # Call appropriate function based on the model ID
    if model_id.startswith('amazon.titan-image') or model_id in IMAGE_MODEL_IDS.values():
        result = get_image_response(model_id, prompt)
    else:
        result = get_text_response(model_id, prompt)

    return build_response(200, result, event)

def call_falcon_model(event):
    """Handles inference with Falcon model deployed on SageMaker."""
    prompt = get_named_parameter(event, 'prompt')

    try:
        response = sagemaker_runtime.invoke_endpoint(
            EndpointName=FALCON_MODEL_ENDPOINT,
            ContentType='application/json',
            Body=json.dumps({"inputs": prompt}).encode('utf-8')  # Corrected encoding
        )
        
        response_body = json.loads(response['Body'].read().decode('utf-8'))
        result = {"result": response_body}
        return build_response(200, result, event)

    except ClientError as e:
        logger.error(f"Error calling Falcon model: {str(e)}")
        return build_response(500, 'Error calling Falcon model', event)

def get_text_response(model_id, prompt):
    """Handles text-based models."""
    if model_id in TEXT_MODEL_IDS:
        return invoke_bedrock_model(bedrock, model_id, prompt)
    else:
        logger.error(f"Unsupported text model ID: {model_id}")
        return {"error": "Unsupported text model ID"}

def get_image_response(model_id, prompt):
    """Handles image generation models."""
    if model_id in IMAGE_MODEL_IDS.values():
        return generate_image_request(model_id, prompt)
    else:
        logger.error(f"Unsupported image model ID: {model_id}")
        return {"error": "Unsupported image model ID"}

def generate_image_request(model_id, prompt):
    """Handles requests for Stable Diffusion and Amazon Titan models."""
    rand_seed = generate_random_seed(0, 4294967295)

    # Handling Stable Diffusion XL models
    if model_id == "stability.stable-diffusion-xl-v1":
        request_body = {
            "text_prompts": [{"text": prompt}],
            "cfg_scale": 10,
            "seed": rand_seed,
            "steps": 50
        }
    elif model_id in ["stability.sd3-large-v1:0", "stability.stable-image-core-v1:0", "stability.stable-image-ultra-v1:0"]:
        request_body = {"prompt": prompt}
    else:
        # Default handling for Amazon Titan and other models
        request_body = {
            "taskType": "TEXT_IMAGE",
            "textToImageParams": {
                "text": prompt
            },
            "imageGenerationConfig": {
                "numberOfImages": 1,
                "quality": "premium",
                "height": 768,
                "width": 1280,
                "cfgScale": 7.5,
                "seed": rand_seed
            }
        }

    return generate_image(model_id, json.dumps(request_body))

def generate_image(model_id, body):
    """Generates an image and uploads it to S3."""
    try:
        response = bedrock.invoke_model(
            body=body, modelId=model_id, accept="application/json", contentType="application/json"
        )
        response_body = json.loads(response.get("body").read())
        base64_image = response_body.get("images")[0]
        image_bytes = base64.b64decode(base64_image)

        # Save and upload image
        local_image_path = "/tmp/generated_image.png"
        image = Image.open(io.BytesIO(image_bytes))
        image.save(local_image_path)
        s3.upload_file(local_image_path, bucket_name, object_name)

        presigned_url = s3.generate_presigned_url('get_object', Params={'Bucket': bucket_name, 'Key': object_name}, ExpiresIn=3600)
        return {"message": "Image generated successfully", "image_url": presigned_url}

    except ClientError as err:
        logger.error(f"Client error: {str(err)}")
        return {"error": "Client error occurred"}
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        return {"error": str(e)}

def generate_random_seed(min_value, max_value):
    """Generates a random seed."""
    return random.randint(min_value, max_value)

def fetch_image_from_s3():
    """Fetches an image from S3 and returns it as a base64-encoded string."""
    image_content = io.BytesIO()
    try:
        s3.download_fileobj(bucket_name, object_name, image_content)
        image_content.seek(0)  
        return base64.b64encode(image_content.getvalue()).decode('utf-8')
    except Exception as e:
        logger.error(f"Error fetching image from S3: {str(e)}")
        return None

def invoke_bedrock_model(client, model_id, prompt, max_tokens=2000, temperature=0, top_p=0.9):
    """Invokes Bedrock text generation API."""
    try:
        response = client.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"temperature": temperature, "maxTokens": max_tokens, "topP": top_p}
        )
        result = response['output']['message']['content'][0]['text'] \
            + '\n--- Latency: ' + str(response['metrics']['latencyMs']) \
            + 'ms - Input tokens:' + str(response['usage']['inputTokens']) \
            + ' - Output tokens:' + str(response['usage']['outputTokens']) + ' ---\n'
        return {"result": result}
    except Exception as e:
        logger.error(f"Model invocation error: {str(e)}")
        return {"error": "Model invocation error"}

def build_response(response_code, result, event):
    """Builds the API response in the required format."""
    action_group = event.get('actionGroup', 'defaultGroup')
    api_path = event.get('apiPath', 'unknown')

    response_body = {
        'application/json': {'body': result}
    }

    action_response = {
        'actionGroup': action_group,
        'apiPath': api_path,
        'httpMethod': event.get('httpMethod', 'POST'),
        'httpStatusCode': response_code,
        'responseBody': response_body
    }

    api_response = {'messageVersion': '1.0', 'response': action_response}
    return api_response
