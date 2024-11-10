import streamlit as st
import requests
import time
import json
import os
from dotenv import load_dotenv
import openai

# ================================
# Load Environment Variables
# ================================

# Load environment variables from .env file
load_dotenv()

# Retrieve API keys and tokens from environment variables
CLIENT_ID = os.getenv('STRAVA_CLIENT_ID')            # Replace with your Strava Client ID
CLIENT_SECRET = os.getenv('STRAVA_CLIENT_SECRET')    # Replace with your Strava Client Secret
AUTHORIZATION_CODE = os.getenv('STRAVA_AUTHORIZATION_CODE')  # Replace with your Strava Authorization Code
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')         # Replace with your OpenAI API Key

# Validate that all required credentials are available
if not CLIENT_ID or not CLIENT_SECRET or not AUTHORIZATION_CODE or not OPENAI_API_KEY:
    st.error("Please ensure all credentials are set in the .env file.")
    st.stop()

# Set OpenAI API key
openai.api_key = OPENAI_API_KEY

TOKEN_FILE = 'strava_tokens.json'

# ================================
# Functions for Token Management
# ================================

def get_access_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as f:
            tokens = json.load(f)
    else:
        tokens = exchange_authorization_code(AUTHORIZATION_CODE)
        if not tokens:
            st.error("Failed to obtain tokens.")
            st.stop()

    current_time = int(time.time())
    if tokens['expires_at'] < current_time:
        tokens = refresh_access_token(tokens['refresh_token'])
        if not tokens:
            st.error("Failed to refresh tokens.")
            st.stop()

    return tokens['access_token']

def exchange_authorization_code(auth_code):
    response = requests.post(
        'https://www.strava.com/oauth/token',
        data={
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'code': auth_code,
            'grant_type': 'authorization_code'
        }
    )

    if response.status_code == 200:
        tokens = response.json()
        save_tokens(tokens)
        return tokens
    else:
        st.error(f"Error exchanging authorization code: {response.text}")
        return None

def refresh_access_token(refresh_token):
    response = requests.post(
        'https://www.strava.com/oauth/token',
        data={
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token
        }
    )

    if response.status_code == 200:
        tokens = response.json()
        save_tokens(tokens)
        return tokens
    else:
        st.error(f"Error refreshing access token: {response.text}")
        return None

def save_tokens(tokens):
    with open(TOKEN_FILE, 'w') as f:
        json.dump(tokens, f)

# ================================
# Functions for Fetching Data
# ================================

def get_athlete_profile(access_token):
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(
        'https://www.strava.com/api/v3/athlete',
        headers=headers
    )
    if response.status_code == 200:
        athlete = response.json()
        return athlete
    else:
        st.error(f"Error fetching athlete profile: {response.text}")
        return None

def get_activities(access_token, num_activities=10):
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(
        'https://www.strava.com/api/v3/athlete/activities',
        headers=headers,
        params={'per_page': num_activities}
    )
    if response.status_code == 200:
        activities = response.json()
        return activities
    else:
        st.error(f"Error fetching activities: {response.text}")
        return []

# ================================
# Function to Construct Prompt
# ================================

def construct_prompt(athlete, activities):
    # Extract bio information
    first_name = athlete.get('firstname', 'Athlete')
    last_name = athlete.get('lastname', '')
    bio = athlete.get('bio', 'No bio available.')
    city = athlete.get('city', 'Unknown city')
    country = athlete.get('country', 'Unknown country')
    sex = athlete.get('sex', 'Not specified')

    # Start constructing the prompt
    prompt = f"""
You are a sarcastic fitness coach. Create a humorous and witty roast for {first_name} {last_name} based on their bio and recent activities.

Bio:
- Name: {first_name} {last_name}
- Gender: {sex}
- Location: {city}, {country}
- Bio Description: {bio}

Recent Activities:
"""

    # Include full information for each activity
    for idx, activity in enumerate(activities, 1):
        name = activity.get('name', 'Unnamed Activity')
        activity_type = activity.get('type', 'Unknown')
        distance = activity.get('distance', 0) / 1000  # Convert to km
        moving_time = activity.get('moving_time', 0) / 60  # Convert to minutes
        average_speed = activity.get('average_speed', 0) * 3.6  # Convert to km/h
        elevation_gain = activity.get('total_elevation_gain', 0)  # in meters
        start_date = activity.get('start_date_local', 'Unknown Date')
        description = activity.get('description', 'No description provided.')

        # Truncate the description if too long
        max_description_length = 200  # Adjust as needed
        description = (description[:max_description_length] + '...') if len(description) > max_description_length else description

        prompt += f"""
Activity {idx}:
- Name: {name}
- Date: {start_date}
- Type: {activity_type}
- Distance: {distance:.2f} km
- Moving Time: {moving_time:.1f} minutes
- Average Speed: {average_speed:.2f} km/h
- Elevation Gain: {elevation_gain:.2f} m
- Description: {description}
"""

    prompt += """
Be creative, but keep it friendly and avoid offensive language. The roast should be in three paragraphs, each focusing on different aspects of the bio and activities.
"""
    return prompt

# ================================
# Function to Generate Roast
# ================================

def generate_roast(prompt):
    try:
        with st.spinner('Generating roast...'):
            completion = openai.chat.completions.create(
                model="gpt-4",  # Ensure this is the correct model name
                messages=[
                    {"role": "system", "content": "You are a sarcastic fitness coach who provides humorous roasts based on user's bio and workout data."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.8,
            )
            roast = completion.choices[0].message.content
        return roast
    except Exception as e:
        return f"Error generating roast: {e}"

# ================================
# Streamlit App
# ================================

def main():
    st.title("Roast My Strava")
    st.write("This app fetches your Strava bio and recent activities to provide an AI-generated roast.")

    # Get the access token
    access_token = get_access_token()

    # Fetch athlete profile
    athlete = get_athlete_profile(access_token)

    if athlete:
        # Fetch last 10 activities
        activities = get_activities(access_token, num_activities=10)

        if activities:
            # Construct the prompt
            prompt = construct_prompt(athlete, activities)

            # Generate the roast
            roast = generate_roast(prompt)

            # Display the bio
            st.subheader("Your Bio")
            st.write(f"**Name:** {athlete.get('firstname', '')} {athlete.get('lastname', '')}")
            st.write(f"**Gender:** {athlete.get('sex', 'Not specified')}")
            st.write(f"**Location:** {athlete.get('city', 'Unknown city')}, {athlete.get('country', 'Unknown country')}")
            st.write(f"**Bio Description:** {athlete.get('bio', 'No bio available.')}")
            st.write("---")

            # Optionally display the activities with descriptions
            if st.checkbox("Show detailed activities with descriptions"):
                st.subheader("Recent Activities")
                for idx, activity in enumerate(activities, 1):
                    name = activity.get('name', 'Unnamed Activity')
                    activity_type = activity.get('type', 'Unknown')
                    distance = activity.get('distance', 0) / 1000  # Convert to km
                    moving_time = activity.get('moving_time', 0) / 60  # Convert to minutes
                    average_speed = activity.get('average_speed', 0) * 3.6  # Convert to km/h
                    elevation_gain = activity.get('total_elevation_gain', 0)  # in meters
                    start_date = activity.get('start_date_local', 'Unknown Date')
                    description = activity.get('description', 'No description provided.')

                    # Truncate the description if too long
                    max_description_length = 200  # Adjust as needed
                    description = (description[:max_description_length] + '...') if len(description) > max_description_length else description

                    st.write(f"**Activity {idx}: {name}**")
                    st.write(f"- **Date:** {start_date}")
                    st.write(f"- **Type:** {activity_type}")
                    st.write(f"- **Distance:** {distance:.2f} km")
                    st.write(f"- **Moving Time:** {moving_time:.1f} minutes")
                    st.write(f"- **Average Speed:** {average_speed:.2f} km/h")
                    st.write(f"- **Elevation Gain:** {elevation_gain:.2f} m")
                    st.write(f"- **Description:** {description}")
                    st.write("---")

            # Display the roast
            st.subheader("Your Personalized Roast")
            st.write(roast)
        else:
            st.write("No activities found.")
    else:
        st.write("Could not retrieve athlete profile.")

if __name__ == '__main__':
    main()