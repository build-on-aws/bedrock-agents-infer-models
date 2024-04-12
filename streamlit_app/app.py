import invoke_agent as agenthelper
import streamlit as st
import json
import pandas as pd
from PIL import Image, ImageOps, ImageDraw
import re

live_session_id = "MYSESSION"
image_name = 'the_image.png'


# Streamlit page configuration
st.set_page_config(page_title="Call Multiple Models Agent", page_icon=":robot_face:", layout="wide")

# Function to crop image into a circle
def crop_to_circle(image):
    mask = Image.new('L', image.size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0) + image.size, fill=255)
    result = ImageOps.fit(image, mask.size, centering=(0.5, 0.5))
    result.putalpha(mask)
    return result

# Title
st.title("Multiple Models Agent")

# Display a text box for request & engineering prompmt
engineering_prompt = st.text_input("Advanced prompt (Optional): ", max_chars=2000)
engineering_prompt = engineering_prompt.strip()

request_prompt = st.text_input("Please enter the request prompt: ", max_chars=10000)
request_prompt = request_prompt.strip()

# Display a primary button for submission
submit_button = st.button("Submit", type="primary")

# Create a file uploader widget
#uploaded_file = st.file_uploader("", type=['jpg', 'jpeg', 'png'])

# Check if a file has been uploaded
# if uploaded_file is not None:
#     result_message = agenthelper.upload_image_to_s3(uploaded_file)
#     st.write(result_message)

#     # Display the uploaded image
#     st.image(uploaded_file, caption='Uploaded Image.', width=300)
# else:
#     st.write("Please upload an image file.")





# Sidebar for user input
st.sidebar.title("Trace Data")

# Session State Management
if 'history' not in st.session_state:
    st.session_state['history'] = []


def format_link(text):
    # Regular expression to find URLs
    url_pattern = r'(https?://\S+)'
    # Replace URLs in the text with Markdown links using "link" as the display text
    formatted_text = re.sub(url_pattern, r'[Click here](\1)', text)
    return formatted_text


# Function to parse and format response
def format_response(response_body):
    try:
        # Try to load the response as JSON
        data = json.loads(response_body)
        # If it's a list, convert it to a DataFrame for better visualization
        if isinstance(data, list):
            return pd.DataFrame(data)
        else:
            return response_body
    except json.JSONDecodeError:
        # If response is not JSON, return as is
        return response_body

# Handling user input and responses
if submit_button and request_prompt:
    # Concatenating engineering_prompt with request_prompt if provided
    combined_prompt = f"{request_prompt} - {engineering_prompt}" if engineering_prompt else request_prompt
    
    event = {
        "sessionId": live_session_id,
        "question": combined_prompt
    }
    
    response = agenthelper.lambda_handler(event, None)
    
    try:
        # Parse the JSON string
        if response and 'body' in response and response['body']:
            response_data = json.loads(response['body'])
            print("TRACE & RESPONSE DATA ->  ", response_data)
        else:
            print("Invalid or empty response received")
    except json.JSONDecodeError as e:
        print("JSON decoding error:", e)
        response_data = None 
    
    try:
        # Extract the response and trace data
        all_data = format_response(response_data['response'])
        the_response = response_data['trace_data']
    except:
        all_data = "..." 
        the_response = "Apologies, but an error occurred. Please rerun the application" 

    # Use trace_data and formatted_response as needed
    st.sidebar.text_area("", value=all_data, height=300)
    st.session_state['history'].append({"question": combined_prompt, "answer": the_response})
    st.session_state['trace_data'] = the_response


submit_button2 = st.button("Delete Image", type="primary")


# Display conversation history
st.write("## Conversation History")

# Load images outside the loop to optimize performance
human_image = Image.open('images/human_face.png')
robot_image = Image.open('images/robot_face.jpg')
circular_human_image = crop_to_circle(human_image)
circular_robot_image = crop_to_circle(robot_image)

# Before displaying conversation history

for index, chat in enumerate(reversed(st.session_state['history'])):
    formatted_question = format_link(chat["question"])
    formatted_answer = format_link(chat["answer"])
    
    # Creating columns for Question
    col1_q, col2_q = st.columns([2, 10])
    with col1_q:
        st.image(circular_human_image, width=125)
    with col2_q:
        st.text_area("Q:", value=formatted_question, height=50, key=f"question_{index}", disabled=True)

    # Creating columns for Answer
    col1_a, col2_a = st.columns([2, 10])
    if isinstance(chat["answer"], pd.DataFrame):
        with col1_a:
            st.image(circular_robot_image, width=100)
        with col2_a:
            st.dataframe(chat["answer"], key=f"answer_df_{index}")
    else:
        with col1_a:
            st.image(circular_robot_image, width=150)
        with col2_a:
            # Directly use st.markdown to render the answer with clickable links
            st.markdown(formatted_answer, unsafe_allow_html=True)


# Add a delete button
if submit_button2:
    # Call the delete function
    agenthelper.delete_file_from_s3('bedrock-agent-images', image_name)
    st.success('Generated image deleted successfully.')

# Example Prompts Section
st.write("## Model Prompts")

# Anthropic Prompts
anthropic_prompts1 = [
    {"Prompt": "Use model anthropic.claude-3-haiku-20240307-v1:0 and describe to me the image that is uploaded. The model function will have the information needed to provide a response. So, dont ask about the image.", 
     "Usecase": "Image-to-text"},
    {"Prompt": "Use model anthropic.claude-3-sonnet-20240229-v1:0 and describe to me the image that is uploaded. Then, provide a rating score based on your image description versus to my last ask of generating an image for me. Explain your reasoning for the answer in detail.", 
     "Usecase": "Image-to-text & comparison"},
     {"Prompt": "Use model anthropic.claude-3-haiku-20240307-v1:0 and describe to me the image that is uploaded. then from this description, use model stability.stable-diffusion-xl-v1 to create an image.",
      "Usecase": "Image-to-text to text-to-image"},
     {
    "Prompt": "Use model anthropic.claude-3-haiku-20240307-v1:0 to create a sql query that only fetches procedures in the dental category that are insured. Refer to the example queries and tables.",
    "Usecase": "Text-to-sql",
    "Advanced prompt": {
    "Customers & Procedures table": "CUSTOMERS TABLE: CREATE EXTERNAL TABLE athena_db.customers (`Cust_Id` integer, `Customer` string, `Balance` integer, `Past_Due` integer, `Vip` string) ROW FORMAT DELIMITED FIELDS TERMINATED BY ',' LINES TERMINATED BY '\\n' STORED AS TEXTFILE LOCATION 's3://athena-datasource-alias/'; PROCEDURES TABLE: CREATE EXTERNAL TABLE athena_db.procedures (`Procedure_ID` string, `Procedure` string, `Category` string, `Price` integer, `Duration` integer, `Insurance` string, `Customer_Id` integer) ROW FORMAT DELIMITED FIELDS TERMINATED BY ',' LINES TERMINATED BY '\\n' STORED AS TEXTFILE LOCATION 's3://athena-datasource-alias/'; ExampleQueries: SELECT * FROM athena_db.procedures WHERE insurance = 'yes'; SELECT * FROM athena_db.customers WHERE balance >= 0;"
    }
    },
      
]

anthropic_prompts2 = [
    {"Prompt": "use model anthropic.claude-3-haiku-20240307-v1:0 and tell me some things that most people are happy for, and afraid of.", 
     "Usecase": "Text generation"},
    {"Prompt": "Use model anthropic.claude-3-sonnet-20240229-v1:0 and write a sonnet about a lost kingdom",
     "Usecase": "Text generation"},
    {"Prompt": "Use model anthropic.claude-v2:1 for a summary of the latest climate change research findings",
     "Usecase": "Summarization"},
    {"Prompt": "Use model anthropic.claude-instant-v1 and give an instant response to: What is the essence of happiness?",
     "Usecase": "Instant response"}
]

# Mistral Prompts
mistral_prompts = [
    {
    "Prompt": "Use model mistral.mixtral-8x7b-instruct-v0:1 to create a sql query that only fetches customers that have a past due amount over 50, and are vip. Refer to the example queries and tables.",
    "Usecase": "Text-to-SQL",
    "Advanced prompt": {
        "Advanced prompt": {
        "Customers & Procedures table": "CUSTOMERS TABLE: CREATE EXTERNAL TABLE athena_db.customers (`Cust_Id` integer, `Customer` string, `Balance` integer, `Past_Due` integer, `Vip` string) ROW FORMAT DELIMITED FIELDS TERMINATED BY ',' LINES TERMINATED BY '\\n' STORED AS TEXTFILE LOCATION 's3://athena-datasource-alias/'; PROCEDURES TABLE: CREATE EXTERNAL TABLE athena_db.procedures (`Procedure_ID` string, `Procedure` string, `Category` string, `Price` integer, `Duration` integer, `Insurance` string, `Customer_Id` integer) ROW FORMAT DELIMITED FIELDS TERMINATED BY ',' LINES TERMINATED BY '\\n' STORED AS TEXTFILE LOCATION 's3://athena-datasource-alias/'; ExampleQueries: SELECT * FROM athena_db.procedures WHERE insurance = 'yes'; SELECT * FROM athena_db.customers WHERE balance >= 0;",
        }
    }
    },
    {
    "Prompt": "Use model mistral.mistral-large-2402-v1:0. Calculate the difference in payment dates between the two customers whose payment amounts are closest to each other in the given dataset, then provide the steps you took to solve it.",
    "Usecase": "Problem solving",
    "Advanced prompt": "{\"transaction_id\":{\"0\":\"T1001\",\"1\":\"T1002\",\"2\":\"T1003\",\"3\":\"T1004\",\"4\":\"T1005\"}, \"customer_id\":{\"0\":\"C001\",\"1\":\"C002\",\"2\":\"C003\",\"3\":\"C002\",\"4\":\"C001\"}, \"payment_amount\":{\"0\":125.5,\"1\":89.99,\"2\":120.0,\"3\":54.3,\"4\":210.2}, \"payment_date\":{\"0\":\"2021-10-05\",\"1\":\"2021-10-06\",\"2\":\"2021-10-07\",\"3\":\"2021-10-05\",\"4\":\"2021-10-08\"}, \"payment_status\":{\"0\":\"Paid\",\"1\":\"Unpaid\",\"2\":\"Paid\",\"3\":\"Paid\",\"4\":\"Pending\"}}"
        
    },
    {"Prompt": "Use model mistral.mistral-7b-instruct-v0:2 and tell me in Bash, how do I list all text files in the current directory (excluding subdirectories) that have been modified in the last month?",
     "Usecase": "Code generation"},
    {"Prompt": "Use model mistral.mistral-7b-instruct-v0:2 and tell me what is the difference between inorder and preorder traversal? Give an example in Python.",
     "Usecase": "Q&A and Code Generation"},
]




# Meta Prompts
meta_prompts = [
    {"Prompt": "Use model meta.llama2-13b-chat-v1 and figure out the following: You are a very intelligent bot with exceptional critical thinking. I went to the market and bought 10 apples. I gave 2 apples to your friend and 2 to the helper. I then went and bought 5 more apples and ate 1. How many apples did I remain with? Provide step by step how you solved it.",
     "Usecase": "Math"},
    {"Prompt": "now use model meta.llama2-70b-chat-v1 and figure out the following: You are a very intelligent bot with exceptional critical thinking. I went to the market and bought 10 apples. I gave 2 apples to your friend and 2 to the helper. I then went and bought 5 more apples and ate 1. How many apples did I remain with? Provide step by step how you solved it. Then, compare it with the previous answer.",
     "Usecase": "Math & compare models"}
]

# Amazon Prompts
amazon_prompts = [
    {"Prompt": "Use model amazon.titan-image-generator-v1 and create me an image of a woman in a boat on a river.",
     "Usecase": "Text-to-image"},
    {"Prompt": "Use model amazon.titan-text-express-v1. Meeting transcript is the following - Miguel: Hi Brant, I want to discuss the workstream for our new product launch Brant: Sure Miguel, is there anything in particular you want to discuss? Miguel: Yes, I want to talk about how users enter into the product. Brant: Ok, in that case let me add in Namita. Namita: Hey everyone Brant: Hi Namita, Miguel wants to discuss how users enter into the product. Miguel: its too complicated and we should remove friction. for example, why do I need to fill out additional forms? I also find it difficult to find where to access the product when I first land on the landing page. Brant: I would also add that I think there are too many steps. Namita: Ok, I can work on the landing page to make the product more discoverable but brant can you work on the additional forms? Brant: Yes but I would need to work with James from another team as he needs to unblock the sign up workflow. Miguel can you document any other concerns so that I can discuss with James only once? Miguel: Sure. - From the meeting transcript above, Create a list of action items for each person.",
     "Usecase": "Summarization"},
    {"Prompt": "Use model amazon.titan-text-lite-v1. Product: Sunglasses. Keywords: polarized, designer, comfortable, UV protection, aviators. Create a table that contains five variations of a detailed product description for the product listed above, each variation of the product description must use all the keywords listed.",
     "Usecase": "Open ended text generation"}
]

# Stability AI Prompts
stability_ai_prompts = [
    {"Prompt": "Use model stability.stable-diffusion-xl-v0. Create an image of an astronaut riding a horse in the desert.",
     "Usecase": "Text-to-image"},
    {"Prompt": "Use model stability.stable-diffusion-xl-v1 to generate what a group of people would look like upset in the middle of an arena.",
     "Usecase": "Text-to-image"},
    {"Prompt": "Use model stability.stable-diffusion-xl-v1. Create an image of a hard working person in front of a food market.",
     "Usecase": "Text-to-image"}
]

# Cohere Prompts
cohere_prompts = [
    {"Prompt": "Use model cohere.command-text-v14. Extract the band name from the contract: This Music Recording Agreement (Agreement) is made effective as of the 13 day of December, 2021 by and between Good Kid, a Toronto-based musical group (Artist) and Universal Music Group, a record label with license number 545345 (Recording Label). Artist and Recording Label may each be referred to in this Agreement individually as a Party and collectively as the Parties. Work under this Agreement shall begin on March 15, 2022.",
     "Usecase": "Open ended text generation"}
]

# AI21labs Prompts
ai21labs_prompts = [
    {"Prompt": "Use model ai21.j2-mid-v1. You are a gifted copywriter, with special expertise in writing Google ads. You are tasked to write a persuasive and personalized Google ad based on a company name and a short description. You need to write the Headline and the content of the Ad itself. For example: Company: Upwork Description: Freelancer marketplace Headline: Upwork: Hire The Best - Trust Your Job To True Experts Ad: Connect your business to Expert professionals & agencies with specialized talent. Post a job today to access Upwork's talent pool of quality professionals & agencies. Grow your team fast. 90% of customers rehire. Trusted by 5M+ businesses. Secure payments. - Write a persuasive and personalized Google ad for the following company. Company: Click Description: SEO services",
     "Usecase": "Text generation"}
]

knowledge_base_model_promt = [
    {"Prompt": "Provide me a description about inflation and rising prices from the FOMC reports.",
     "Usecase": "RAG"}
]

image_generate_and_rate_prompt = [
    {"Prompt": "Use model amazon.titan-image-generator-v1. Create me a pie chart that shows a 70 percent sales growth. Use model anthropic.claude-3-sonnet-20240229-v1:0 and describe to me the image that is uploaded. Then use the same model to give me a confidence score and explain your reasoning. Dont ask about the image, because the model function will have the information needed to provide a response.",
     "Usecase": "Image generation & rating"}
]



# Displaying the prompts as tables

st.write("### Amazon Models")
st.table(amazon_prompts)

st.write("### Anthropic Models")
st.write("#### The anthropic prompts below are image-to-text inference calls, which will call the image-to-text anthropic function IF the the_image.png file is detected in the S3 bucket.")
st.table(anthropic_prompts1)
st.write("#### Remove the mypic.png image from the S3 bucket before running the anthropic prompts below. This will call the text anthropic function if the image is NOT detected in the S3 bucket. If not, the response may have descrepency.")
st.table(anthropic_prompts2)

st.write("### Stability AI Models")
st.table(stability_ai_prompts)

st.write("### Mistral Models")
st.table(mistral_prompts)

st.write("### Meta Models")
st.table(meta_prompts)

st.write("### Cohere Models")
st.table(cohere_prompts)

st.write("### AI21labs Models")
st.table(ai21labs_prompts)

st.write("### Amazon & Claude Model")
st.table(image_generate_and_rate_prompt)

#st.write("### RAG")
#st.table(knowledge_base_model_promt)


# Display a button to end the session
end_session_button = st.button("End Session")

if end_session_button:
    st.session_state['history'].append({"question": "Session Ended", "answer": "Thank you for using AnyCompany Support Agent!"})
    event = {
        "sessionId": live_session_id,
        "question": "placeholder to end session",
        "endSession": True
    }
    agenthelper.lambda_handler(event, None)
    st.session_state['history'].clear()