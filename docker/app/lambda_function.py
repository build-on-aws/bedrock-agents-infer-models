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
object_name = 'generated_image.png'
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
        """Fetches an image from an S3 bucket and returns it as a base64-encoded string."""
        image_content = io.BytesIO()
        try:
            s3.download_fileobj(bucket_name, object_name, image_content)
            image_content.seek(0)  # Move to the beginning of the file
            
            # Encode the image in base64
            encoded_image = base64.b64encode(image_content.getvalue()).decode('utf-8')
            print("Image successfully fetched and encoded from S3.")
            return encoded_image
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
            # Example for a v2 model with a reference image, encoded in base64
            reference_image_base64 = fetch_image_from_s3()
            if not reference_image_base64:
                return {"statusCode": 500, "body": json.dumps({"error": "Failed to fetch reference image from S3"})}
            
            request_body = json.dumps({
                "taskType": "TEXT_IMAGE",
                "textToImageParams": {
                    "text": prompt_content,
                    "conditionImage": reference_image_base64,
                    "controlMode": "CANNY_EDGE",
                    "controlStrength": 0.7
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
        """Generates an image using Amazon Titan Image Generator and stores it in S3."""
        logger.info(f"Generating image with Amazon Titan Image Generator model {model_id}")
        accept = "application/json"
        content_type = "application/json"

        try:
            # Invoke the Bedrock API
            response = bedrock.invoke_model(
                body=body, modelId=model_id, accept=accept, contentType=content_type
            )
            response_body = json.loads(response.get("body").read())
            base64_image = response_body.get("images")[0]

            # Decode the base64 image data
            image_bytes = base64.b64decode(base64_image)
            image = Image.open(io.BytesIO(image_bytes))

            # Save image locally in the Lambda /tmp directory
            local_image_path = "/tmp/generated_image.png"
            image.save(local_image_path)

            # Upload the image to S3
            s3.upload_file(local_image_path, bucket_name, object_name)

            # Generate a presigned URL to the uploaded image in S3
            presigned_url = s3.generate_presigned_url('get_object', Params={'Bucket': bucket_name, 'Key': object_name}, ExpiresIn=3600)

            # Return the presigned URL instead of the base64 string
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "message": "Image generated successfully",
                    "image_url": presigned_url
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
