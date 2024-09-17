import json
import os
import base64
import logging
import boto3
import io
from PIL import Image, ImageOps
from botocore.exceptions import ClientError

s3 = boto3.client('s3')

sts_client = boto3.client('sts')
account_id = sts_client.get_caller_identity().get('Account')
region = boto3.Session().region_name
bedrock = boto3.client(service_name='bedrock-runtime', region_name=region)

# Construct the S3 bucket name
bucket_name = f"bedrock-agent-images-{account_id}-{region}"
os.environ['S3_IMAGE_BUCKET'] = bucket_name
object_name = 'the_image.png'
logger = logging.getLogger(__name__)

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

def lambda_handler(event, context):
    print(event)
    
    def get_named_parameter(event, name):
        return next(item for item in event['parameters'] if item['name'] == name)['value']

    model_id = get_named_parameter(event, 'modelId')
    prompt = get_named_parameter(event, 'prompt')
    print("MODEL ID: " + model_id)
    print("PROMPT: " + prompt)

    def fetch_image_from_s3():
        """Fetches an image from an S3 bucket and returns it as a BytesIO object."""
        image_content = io.BytesIO()
        try:
            s3.download_fileobj(bucket_name, object_name, image_content)
            print("Image successfully fetched from S3.")
            return image_content
        except Exception as e:
            print(f"Error fetching image from S3: {e}")
            return None

    def get_image_response(prompt_content):
        """Handles image generation models."""
        if model_id == 'amazon.titan-image-generator-v1':
            request_body = json.dumps({
                "taskType": "TEXT_IMAGE",
                "textToImageParams": {
                    "text": prompt_content
                },
                "imageGenerationConfig": {
                    "numberOfImages": 1,
                    "quality": "standard",
                    "height": 1024,
                    "width": 1024,
                    "cfgScale": 7.5,
                    "seed": 42
                }
            })

        elif model_id == 'amazon.titan-image-generator-v2:0':
            # Example for a v2 model with a reference image, adjust as needed
            reference_image_base64 = fetch_image_from_s3()
            request_body = json.dumps({
                "taskType": "TEXT_IMAGE",
                "textToImageParams": {
                    "text": prompt_content,
                    "conditionImage": reference_image_base64, # Optionally condition on an image
                    "controlMode": "CANNY_EDGE", # Example mode
                    "controlStrength": 0.7       # Example control strength
                },
                "imageGenerationConfig": {
                    "numberOfImages": 1,
                    "seed": 42
                }
            })

        else:
            logger.error(f"Unsupported image model ID: {model_id}")
            return "Unsupported image model ID."

        return generate_image(model_id, request_body)

    def generate_image(model_id, body):
        """Generates an image using Amazon Titan Image Generator."""
        logger.info(f"Generating image with Amazon Titan Image Generator model {model_id}")
        accept = "application/json"
        content_type = "application/json"

        try:
            response = bedrock.invoke_model(
                body=body, modelId=model_id, accept=accept, contentType=content_type
            )
            response_body = json.loads(response.get("body").read())
            base64_image = response_body.get("images")[0]

            # Decode the base64 image
            image_bytes = base64.b64decode(base64_image)
            image = Image.open(io.BytesIO(image_bytes))

            # Save image locally or process it further if needed
            output_image_path = "/tmp/generated_image.png"
            image.save(output_image_path)

            # Optionally, upload the image back to S3 or provide a presigned URL for access
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "message": "Image generated successfully",
                    "image_base64": base64_image
                })
            }

        except ClientError as err:
            message = err.response["Error"]["Message"]
            logger.error("A client error occurred: %s", message)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": message})
            }
        except Exception as e:
            logger.error(f"An error occurred: {str(e)}")
            return {
                "statusCode": 500,
                "body": json.dumps({"error": str(e)})
            }

    def image_to_base64(img):
        """Converts a PIL Image or BytesIO object to a base64 string."""
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def invoke_bedrock_model(client, id, prompt, max_tokens=2000, temperature=0, top_p=0.9):
        """Invokes the converseAPI for text generation models."""
        try:
            response = client.converse(
                modelId=id,
                messages=[{
                    "role": "user",
                    "content": [{"text": prompt}]
                }],
                inferenceConfig={
                    "temperature": temperature,
                    "maxTokens": max_tokens,
                    "topP": top_p
                }
            )
            result = response['output']['message']['content'][0]['text'] \
                + '\n--- Latency: ' + str(response['metrics']['latencyMs']) \
                + 'ms - Input tokens:' + str(response['usage']['inputTokens']) \
                + ' - Output tokens:' + str(response['usage']['outputTokens']) + ' ---\n'
            return result
        except Exception as e:
            logger.error(f"Model invocation error: {str(e)}")
            return "Model invocation error"

    def get_text_response(model_id, prompt):
        """Handles text-based models using the converseAPI."""
        if model_id in TEXT_MODEL_IDS:
            return invoke_bedrock_model(bedrock, model_id, prompt)
        else:
            logger.error(f"Unsupported text model ID: {model_id}")
            return "Unsupported text model ID."

    try:
        if model_id.startswith('stability') or model_id.startswith('amazon.titan-image'):
            # Handle image generation
            response = get_image_response(prompt)
        else:
            # Handle text generation
            response = get_text_response(model_id, prompt)
        
        print(response)
    except ClientError as e:
        logger.error(f"Client error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")

    # Action group response
    response_code = 200
    action_group = event['actionGroup']
    api_path = event['apiPath']

    if api_path == '/callModel':
        result = response
    else:
        response_code = 404
        result = f"Unrecognized api path: {action_group}::{api_path}"

    response_body = {
        'application/json': {'body': result}
    }

    action_response = {
        'actionGroup': action_group,
        'apiPath': api_path,
        'httpMethod': event['httpMethod'],
        'httpStatusCode': response_code,
        'responseBody': response_body
    }

    api_response = {'messageVersion': '1.0', 'response': action_response}
    return api_response
