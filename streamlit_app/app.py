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

# Model ID dropdown
model_ids = [
    #"anthropic.claude-3-opus-20240229-v1:0",
    "anthropic.claude-3-haiku-20240307-v1:0",
    "anthropic.claude-3-sonnet-20240229-v1:0",
    "anthropic.claude-v2:1",
    "anthropic.claude-v2",
    "anthropic.claude-instant-v1",
    "mistral.mistral-large-2402-v1:0",
    "mistral.mistral-7b-instruct-v0:2",
    "mistral.mixtral-8x7b-instruct-v0:1",
    "amazon.titan-text-lite-v1",
    "amazon.titan-text-express-v1",
    "amazon.titan-image-generator-v1",
    "meta.llama3-8b-instruct-v1:0",
    "meta.llama3-70b-instruct-v1:0",
    "meta.llama2-13b-chat-v1",
    "meta.llama2-70b-chat-v1",
    "cohere.command-text-v14",
    "cohere.command-light-text-v14",
    "stability.stable-diffusion-xl-v0",
    "stability.stable-diffusion-xl-v1",
    "ai21.j2-ultra-v1",
    "ai21.j2-mid-v1"
]

#selected_model_id = st.selectbox("Select a model ID:", model_ids)

request_prompt = st.text_input("Please enter the request prompt: ", max_chars=10000)
request_prompt = request_prompt.strip()

# Display a text box for request & engineering prompmt
engineering_prompt = st.text_input("Advanced prompt (Optional): ", max_chars=10000)
engineering_prompt = engineering_prompt.strip()


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
    #combined_prompt = f"Use model id {selected_model_id} to {request_prompt}"
    if engineering_prompt:
        request_prompt += f" - {engineering_prompt}" 
    event = {
        "sessionId": live_session_id,
        "question": request_prompt
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
    st.session_state['history'].append({"question": request_prompt, "answer": the_response})
    st.session_state['trace_data'] = the_response


submit_button2 = st.button("Delete Image", type="primary")


# Display conversation history
st.write("## Conversation History")

# Load images outside the loop to optimize performance
human_image = Image.open('app/streamlit_app/images/human_face.png')
robot_image = Image.open('app/streamlit_app/images/robot_face.jpg')
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

meeting_transcript = (
    "Meeting Transcript\n\n"
    "Date: July 8, 2024\n"
    "Time: 10:00 AM - 11:00 AM\n"
    "Location: Conference Room A\n"
    "Attendees:\n"
    "- John Smith (Project Manager)\n"
    "- Jane Doe (Software Engineer)\n"
    "- Mike Johnson (Data Analyst)\n"
    "- Sara Lee (Product Owner)\n"
    "- Emma Wilson (UX Designer)\n\n"
    "John Smith: Good morning, everyone. Thank you for joining today's meeting. We have a few important items on the agenda. Let's start with a quick project update. Jane, could you please give us an overview of the current status?\n\n"
    "Jane Doe: Sure, John. As of now, the development team is on track with the sprint goals. We've completed the integration of the new API, and the initial testing looks good. We're currently focusing on the front-end enhancements, which should be wrapped up by the end of this week.\n\n"
    "John Smith: That's great to hear. Mike, can you provide us with an update on the data analysis side?\n\n"
    "Mike Johnson: Absolutely. We've gathered the latest user interaction data and have identified a few key trends. One interesting insight is that users are spending more time on the new features we introduced last quarter. We're working on a detailed report which should be ready by early next week.\n\n"
    "John Smith: Excellent. Sara, do you have any updates from the product side?\n\n"
    "Sara Lee: Yes, John. We've been collecting feedback from the beta testers, and overall, the response has been positive. There are a few areas where users have suggested improvements, particularly in the navigation flow. Emma and I will be reviewing this feedback in more detail to prioritize changes for the next release.\n\n"
    "John Smith: Thank you, Sara. Emma, do you have anything to add regarding the UX design?\n\n"
    "Emma Wilson: Yes, I’ve been working on some new wireframes based on the feedback we've received. I’ll share these with the team later today for review. The goal is to simplify the user journey and make the interface more intuitive.\n\n"
    "John Smith: Great. Now, let's discuss the upcoming milestones and deadlines. We have a major release scheduled for the end of the month. Jane, do you foresee any potential blockers that we need to address?\n\n"
    "Jane Doe: At the moment, everything seems to be on track. However, we do need to ensure that the QA team has enough time to thoroughly test the new features. I'll coordinate with them to ensure we stay on schedule.\n\n"
    "John Smith: That's a good point. Mike, please make sure that any data-related tasks are completed in time for the QA phase.\n\n"
    "Mike Johnson: Will do, John. I'll work closely with the QA team to provide them with all the necessary data and reports.\n\n"
    "John Smith: Perfect. Sara, Emma, any additional support needed from the development team for the UX improvements?\n\n"
    "Sara Lee: Not at this stage, but we’ll keep you updated if anything comes up.\n\n"
    "Emma Wilson: Same here. We're good for now, but I'll reach out if we need any help.\n\n"
    "John Smith: Alright, thank you, everyone. Let's reconvene next week to review our progress. Please ensure all action items are updated in our project management tool by the end of today. Have a great day!\n\n"
    "Meeting adjourned at 11:00 AM."
)


# Model prompts structured for Streamlit display
model_prompts = [
    {
        'title': 'Amazon Titan Models',
        'prompts': [
            {"Model ID": "amazon.titan-image-generator-v1", "Prompt": "Use model id amazon.titan-image-generator-v1 and create an image of a woman in a boat on a river.", "Schema(Adv. prompt)": "N/A", "Usecase": "Text-to-image"},
            {"Model ID": "amazon.titan-text-express-v1", "Prompt": "Use model id amazon.titan-text-express-v1. From the meeting transcript provided, create a list of action items for each person.", "Schema(Adv. prompt)": meeting_transcript, "Usecase": "Summarization"},
            {"Model ID": "amazon.titan-text-lite-v1", "Prompt": "Use model id amazon.titan-text-lite-v1 and create a table that contains five variations of a detailed product description for sunglasses using keywords: polarized, designer, comfortable, UV protection, aviators.", "Schema(Adv. prompt)": "N/A", "Usecase": "Text generation"}
        ]
    },
    {
        'title': 'Meta Models',
        'prompts': [
            {"Model ID": "meta.llama3-8b-instruct-v1:0", "Prompt": "Use model id meta.llama3-8b-instruct-v1:0 and do sentiment analysis with nuances in reasoning of the following: Recently, I purchased a new smartphone from a well-known electronics brand, and I'm thoroughly disappointed. The phone frequently freezes, the battery life is terrible, and the customer service was unhelpful when I reached out for support. I expected much better quality and service based on their reputation.", "Usecase": "Sentiment analysis "},
            {"Model ID": "meta.llama3-70b-instruct-v1:0", "Prompt": "Use model id meta.llama3-70b-instruct-v1:0 and provide me text classification of the following: Global warming is a major environmental issue that is causing the earth's temperatures to rise. This leads to more severe weather patterns, including increased hurricanes, droughts, and floods. Various international organizations are stepping up efforts to reduce carbon emissions and promote green energy solutions to combat climate change.", "Usecase": "Text classification"},

            {"Model ID": "meta.llama2-13b-chat-v1", "Prompt": "Use model id meta.llama2-13b-chat-v1 and solve the following problem: I went to the market and bought 10 apples. I gave 2 to a friend and 2 to a helper, bought 5 more, ate 1. How many apples do I have left?", "Usecase": "Math"},
            {"Model ID": "meta.llama2-70b-chat-v1", "Prompt": "Use model id meta.llama2-70b-chat-v1 and solve the apple problem again and compare it with the previous answer, detailing any differences.", "Usecase": "Math & compare models"}
        ]
    },
    {
        'title': 'Anthropic Models',
        'prompts': [
            #{"Model ID": "anthropic.claude-3-opus-20240229-v1:0", "Prompt": "Describe to me the image that is uploaded. The model function will have the information needed to provide a response.", "Usecase": "Image-to-text"},
            {"Model ID": "anthropic.claude-3-haiku-20240307-v1:0", "Prompt": "Use model id anthropic.claude-3-haiku-20240307-v1:0 and describe to me the image that is uploaded. Then provide a confidence score based on the description I gave and how correctly detailed everything is in the image. Explain your reasoning.", "Usecase": "Image generation & rating"},
            {"Model ID": "anthropic.claude-3-sonnet-20240229-v1:0", "Prompt": "use model id anthropic.claude-3-sonnet-20240229-v1:0 and describe to me the image that is uploaded. Then, from this description, use model stability.stable-diffusion-xl-v1 to create an image.", "Usecase": "Image-to-text to text-to-image"},
            {"Model ID": "anthropic.claude-v2:1", "Prompt": "Use model id anthropic.claude-v2:1 to summarize the latest climate change research findings.", "Usecase": "Summarization"},
            {"Model ID": "anthropic.claude-instant-v1", "Prompt": "Use mondel id anthropic.claude-instant-v1 and provide an instant response to: What is the essence of happiness?", "Usecase": "Instant response"}
        ]
    },
    {
        'title': 'Mistral Models',
        'prompts': [
            {"Model ID": "mistral.mistral-large-2402-v1:0", "Prompt": "Use model id mistral.mistral-large-2402-v1:0 and create a SQL query that only fetches procedures in the dental category that are insured.", "Schema(Adv. prompt)": "CUSTOMERS TABLE: CREATE EXTERNAL TABLE athena_db.customers (`Cust_Id` integer, `Customer` string, `Balance` integer, `Past_Due` integer, `Vip` string) ROW FORMAT DELIMITED FIELDS TERMINATED BY ',' LINES TERMINATED BY '\\n' STORED AS TEXTFILE LOCATION 's3://athena-datasource-alias/'; PROCEDURES TABLE: CREATE EXTERNAL TABLE athena_db.procedures (`Procedure_ID` string, `Procedure` string, `Category` string, `Price` integer, `Duration` integer, `Insurance` string, `Customer_Id` integer) ROW FORMAT DELIMITED FIELDS TERMINATED BY ',' LINES TERMINATED BY '\\n' STORED AS TEXTFILE LOCATION 's3://athena-datasource-alias/'; ExampleQueries: SELECT * FROM athena_db.procedures WHERE insurance = 'yes'; SELECT * FROM athena_db.customers WHERE balance >= 0;", "Usecase": "Text-to-SQL"},
            {"Model ID": "mistral.mistral-7b-instruct-v0:2", "Prompt": "Use model id mistral.mistral-7b-instruct-v0:2 and tell me what is the difference between inorder and preorder traversal? Give an example in Python.", "Usecase": "Q&A and Code Generation"},
            {"Model ID": "mistral.mixtral-8x7b-instruct-v0:1", "Prompt": "Use model id mistral.mixtral-8x7b-instruct-v0:1 and create a SQL query that only fetches customers that have a past due amount over 50, and are VIP.", "Schema(Adv. prompt)": "CUSTOMERS TABLE: CREATE EXTERNAL TABLE athena_db.customers (`Cust_Id` integer, `Customer` string, `Balance` integer, `Past_Due` integer, `Vip` string) ROW FORMAT DELIMITED FIELDS TERMINATED BY ',' LINES TERMINATED BY '\\n' STORED AS TEXTFILE LOCATION 's3://athena-datasource-alias/'; PROCEDURES TABLE: CREATE EXTERNAL TABLE athena_db.procedures (`Procedure_ID` string, `Procedure` string, `Category` string, `Price` integer, `Duration` integer, `Insurance` string, `Customer_Id` integer) ROW FORMAT DELIMITED FIELDS TERMINATED BY ',' LINES TERMINATED BY '\\n' STORED AS TEXTFILE LOCATION 's3://athena-datasource-alias/'; ExampleQueries: SELECT * FROM athena_db.procedures WHERE insurance = 'yes'; SELECT * FROM athena_db.customers WHERE balance >= 0;", "Usecase": "Text-to-SQL"}
        ]
    },
    {
        'title': 'Stability AI Models',
        'prompts': [
            {"Model ID": "stability.stable-diffusion-xl-v0", "Prompt": "Use model id stability.stable-diffusion-xl-v0 to create an image of an astronaut riding a horse in the desert.", "Usecase": "Text-to-image"},
            {"Model ID": "stability.stable-diffusion-xl-v1", "Prompt": "Use model id stability.stable-diffusion-xl-v1 to generate what a group of people would look like upset in the middle of an arena.", "Usecase": "Text-to-image"}
        ]
    },
    {
        'title': 'Cohere Models',
        'prompts': [
            {"Model ID":"cohere.command-text-v14", "Prompt": "Use model id cohere.command-text-v14 to extract the band name from the contract: This Music Recording Agreement (Agreement) is made effective as of the 13 day of December, 2021 by and between Good Kid, a Toronto-based musical group (Artist) and Universal Music Group, a record label with license number 545345 (Recording Label). Artist and Recording Label may each be referred to in this Agreement individually as a Party and collectively as the Parties. Work under this Agreement shall begin on March 15, 2022.", "Usecase": "Text extraction"}
        ]
    },
    {
        'title': 'AI21labs Models',
        'prompts': [
            {"Model ID": "ai21.j2-ultra-v1", "Prompt": "Use model id ai21.j2-ultra-v1. You are a gifted copywriter, tasked to write a persuasive and personalized Google ad based on a company name and a short description. For example: Company: Upwork Description: Freelancer marketplace Headline: Upwork: Hire The Best - Trust Your Job To True Experts Ad: Connect your business to Expert professionals & agencies with specialized talent. Post a job today to access Upwork's talent pool of quality professionals & agencies. Grow your team fast. 90% of customers rehire. Trusted by 5M+ businesses. Secure payments.", "Usecase": "Text generation"},
            {"Model ID": "ai21.j2-mid-v1", "Prompt": "Use model id ai21.j2-mid-v1. Write a persuasive and personalized Google ad for the following company. Company: Click Description: SEO services", "Usecase": "Text generation"}
        ]
    }
]



# Displaying the prompts as tables
st.write("### Model Prompts by Category")
for category in model_prompts:
    st.write(f"#### {category['title']}")
    st.table(category['prompts'])



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
