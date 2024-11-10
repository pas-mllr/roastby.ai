import streamlit as st
import requests
import json
import time
import os
import urllib.parse
import openai

# Strava API endpoints
AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
TOKEN_URL = "https://www.strava.com/oauth/token"

# Retrieve API keys from Streamlit secrets or environment variables
CLIENT_ID = st.secrets.get("STRAVA_CLIENT_ID") or os.getenv('STRAVA_CLIENT_ID')
CLIENT_SECRET = st.secrets.get("STRAVA_CLIENT_SECRET") or os.getenv('STRAVA_CLIENT_SECRET')
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY") or os.getenv('OPENAI_API_KEY')
REDIRECT_URI = st.secrets.get("REDIRECT_URI") or os.getenv('REDIRECT_URI') or 'http://localhost:8501'

# Set OpenAI API key
openai.api_key = OPENAI_API_KEY

# Validate that all required credentials are available
if not CLIENT_ID or not CLIENT_SECRET or not OPENAI_API_KEY or not REDIRECT_URI:
    st.error("Please ensure all credentials are set.")
    st.stop()

def main():
    st.title("Strava Activity Roaster with GPT-4")
    st.write("Welcome! This app fetches your Strava bio and recent activities to provide an AI-generated roast.")

    # Initialize session state
    if 'access_token' not in st.session_state:
        st.session_state['access_token'] = None

    # Check if access token is available
    if st.session_state['access_token'] is None:
        # Check for authorization code in URL
        query_params = st.experimental_get_query_params()
        if 'code' in query_params:
            code = query_params['code'][0]
            # Exchange code for access token
            access_token = exchange_code_for_token(code)
            if access_token:
                st.session_state['access_token'] = access_token
                # Clear query params to clean up URL
                st.experimental_set_query_params()
                st.experimental_rerun()
            else:
                st.error("Failed to get access token.")
        else:
            # Display login button
            if st.button("Login with Strava"):
                # Redirect user to Strava's authorization URL
                auth_url = get_strava_auth_url(REDIRECT_URI)
                # Redirect to the authorization URL
                st.experimental_set_query_params()
                js = f"""<script type="text/javascript">
                        window.location.href = "{auth_url}";
                        </script>"""
                st.markdown(js, unsafe_allow_html=True)
            else:
                st.write("Please log in with Strava to continue.")
    else:
        # User is logged in, proceed to fetch data and generate roast
        run_app_logic()

def get_strava_auth_url(redirect_uri):
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "approval_prompt": "auto",
        "scope": "read,activity:read_all"
    }
    url = f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"
    return url

def exchange_code_for_token(code):
    response = requests.post(
        TOKEN_URL,
        data={
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'code': code,
            'grant_type': 'authorization_code'
        }
    )
    if response.status_code == 200:
        tokens = response.json()
        return tokens['access_token']
    else:
        st.error(f"Error exchanging authorization code: {response.text}")
        return None

def get_athlete_profile():
    headers = {'Authorization': f"Bearer {st.session_state['access_token']}"}
    response = requests.get('https://www.strava.com/api/v3/athlete', headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"Error fetching athlete profile: {response.text}")
        return None

def get_activities(num_activities=5):
    headers = {'Authorization': f"Bearer {st.session_state['access_token']}"}
    response = requests.get(
        'https://www.strava.com/api/v3/athlete/activities',
        headers=headers,
        params={'per_page': num_activities}
    )
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"Error fetching activities: {response.text}")
        return []

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

def generate_roast(prompt):
    try:
        with st.spinner('Generating roast...'):
            completion = openai.chat.completions.create(
                model="gpt-4",
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

def run_app_logic():
    athlete = get_athlete_profile()
    if athlete:
        activities = get_activities(num_activities=5)
        if activities:
            prompt = construct_prompt(athlete, activities)
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