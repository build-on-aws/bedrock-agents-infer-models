import boto3
from boto3.session import Session
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials
import json
import os
from requests import request
import base64
import io
import sys
from PIL import Image

#For this to run on a local machine in VScode, you need to set the AWS_PROFILE environment variable to the name of the profile/credentials you want to use. 
#You also need to input your model ID near the bottom of this file.

#check for credentials
#echo $AWS_ACCESS_KEY_ID
#echo $AWS_SECRET_ACCESS_KEY
#echo $AWS_SESSION_TOKEN


agentId = "xx" #INPUT YOUR AGENT ID HERE
agentAliasId = "xx" # Hits draft alias, set to a specific alias id for a deployed version
bucket_name = 'bedrock-agent-images'
os.environ["AWS_REGION"] = "us-west-2"

image_name = 'the_image.png'


theRegion = os.environ["AWS_REGION"]
region = os.environ.get("AWS_REGION")
llm_response = ""
s3 = boto3.client('s3')

def sigv4_request(
    url,
    method='GET',
    body=None,
    params=None,
    headers=None,
    service='execute-api',
    region=os.environ['AWS_REGION'],
    credentials=Session().get_credentials().get_frozen_credentials()
):
    """Sends an HTTP request signed with SigV4
    Args:
    url: The request URL (e.g. 'https://www.example.com').
    method: The request method (e.g. 'GET', 'POST', 'PUT', 'DELETE'). Defaults to 'GET'.
    body: The request body (e.g. json.dumps({ 'foo': 'bar' })). Defaults to None.
    params: The request query params (e.g. { 'foo': 'bar' }). Defaults to None.
    headers: The request headers (e.g. { 'content-type': 'application/json' }). Defaults to None.
    service: The AWS service name. Defaults to 'execute-api'.
    region: The AWS region id. Defaults to the env var 'AWS_REGION'.
    credentials: The AWS credentials. Defaults to the current boto3 session's credentials.
    Returns:
     The HTTP response
    """

    # sign request
    req = AWSRequest(
        method=method,
        url=url,
        data=body,
        params=params,
        headers=headers
    )
    SigV4Auth(credentials, service, region).add_auth(req)
    req = req.prepare()

    # send request
    return request(
        method=req.method,
        url=req.url,
        headers=req.headers,
        data=req.body
    )

def askQuestion(question, url, endSession=False):
    myobj = {
        "inputText": question,   
        "enableTrace": True,
        "endSession": endSession
    }
    
    # send request
    response = sigv4_request(
        url,
        method='POST',
        service='bedrock',
        headers={
            'content-type': 'application/json', 
            'accept': 'application/json',
        },
        region=theRegion,
        body=json.dumps(myobj)
    ) 
    return decode_response(response)


def delete_file_from_s3(bucket_name, object_name):
    try:
        s3.delete_object(Bucket=bucket_name, Key=object_name)
        print(f"File {object_name} deleted successfully from bucket {bucket_name}.")
    except Exception as e:
        print(f"Error deleting file {object_name} from bucket {bucket_name}: {str(e)}")



def resize_image(image):
    """
    Resize the image to a width of 300 pixels while maintaining aspect ratio.
    
    Parameters:
    - image: PIL Image object.
    
    Returns:
    A byte array of the resized image.
    """
    # Desired width
    target_width = 300

    # Calculate the new height to maintain aspect ratio
    original_width, original_height = image.size
    aspect_ratio = original_height / original_width
    new_height = int(target_width * aspect_ratio)

    # Resize the image
    resized_image = image.resize((target_width, new_height), Image.ANTIALIAS)

    # Convert the resized image to a byte array
    img_byte_arr = io.BytesIO()
    resized_image.save(img_byte_arr, format='PNG')
    
    return img_byte_arr.getvalue()


def upload_image_to_s3(uploaded_file):
    """
    Converts uploaded image to PNG format and uploads to an S3 bucket.
    
    Parameters:
    - uploaded_file: The uploaded file object from Streamlit.
    - bucket_name: The name of the S3 bucket.
    
    Returns:
    A success message if upload succeeds, otherwise an error message.
    """
    # Initialize S3 client
    s3_client = boto3.client('s3')
    
    # Supported image types
    supported_types = ['jpg', 'jpeg', 'png']
    file_type = uploaded_file.type.split('/')[-1]

    if file_type.lower() not in supported_types:
        return "File must be jpg, jpeg, or png."

    try:
        # Convert uploaded file to PIL Image then resize
        image = Image.open(uploaded_file)

        # Convert image to PNG byte array
        img_byte_arr = io.BytesIO()

        image.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()
        #img_byte_arr = resize_image(img_byte_arr)

        # Upload the PNG byte array to S3
        s3_client.put_object(Body=img_byte_arr, Bucket=bucket_name, Key=image_name)

        return "Image successfully uploaded to S3 as 'image.png'."
    except Exception as e:
        # Handle exceptions
        print(e)
        return "Failed to upload the image to S3."
    
    
def decode_response(response):
    # Create a StringIO object to capture print statements
    captured_output = io.StringIO()
    sys.stdout = captured_output

    # Your existing logic
    string = ""
    for line in response.iter_content():
        try:
            string += line.decode(encoding='utf-8')
        except:
            continue

    print("Decoded response", string)
    split_response = string.split(":message-type")
    print(f"Split Response: {split_response}")
    print(f"length of split: {len(split_response)}")

    for idx in range(len(split_response)):
        if "bytes" in split_response[idx]:
            #print(f"Bytes found index {idx}")
            encoded_last_response = split_response[idx].split("\"")[3]
            decoded = base64.b64decode(encoded_last_response)
            final_response = decoded.decode('utf-8')
            print(final_response)
        else:
            print(f"no bytes at index {idx}")
            print(split_response[idx])
            
    last_response = split_response[-1]
    print(f"Lst Response: {last_response}")
    if "bytes" in last_response:
        print("Bytes in last response")
        encoded_last_response = last_response.split("\"")[3]
        decoded = base64.b64decode(encoded_last_response)
        final_response = decoded.decode('utf-8')
    else:
        print("no bytes in last response")
        part1 = string[string.find('finalResponse')+len('finalResponse":'):] 
        part2 = part1[:part1.find('"}')+2]
        final_response = json.loads(part2)['text']

    final_response = final_response.replace("\"", "")
    final_response = final_response.replace("{input:{value:", "")
    final_response = final_response.replace(",source:null}}", "")
    llm_response = final_response

    # Restore original stdout
    sys.stdout = sys.__stdout__

    # Get the string from captured output
    captured_string = captured_output.getvalue()

    # Return both the captured output and the final response
    return captured_string, llm_response


def lambda_handler(event, context):
    sessionId = event["sessionId"]
    question = event["question"]
    endSession = False
    
    print(f"Session: {sessionId} asked question: {question}")
    
    try:
        if (event["endSession"] == "true"):
            endSession = True
    except:
        endSession = False
    
    url = f'https://bedrock-agent-runtime.{theRegion}.amazonaws.com/agents/{agentId}/agentAliases/{agentAliasId}/sessions/{sessionId}/text'

    
    try: 
        response, trace_data = askQuestion(question, url, endSession)

        return {
            "status_code": 200,
            #"body": json.dumps({"response": response, "trace_data": trace_data})
            "body": json.dumps({"response": response, "trace_data": trace_data})
        }
    except Exception as e:
        return {
            "status_code": 500,
            "body": json.dumps({"error": str(e)})
        }


