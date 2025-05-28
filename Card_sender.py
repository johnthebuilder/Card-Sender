import streamlit as st
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import io
import base64
from PIL import Image, ImageDraw, ImageFont
import requests
import json
import os

# Page configuration
st.set_page_config(
    page_title="Birthday Card Manager",
    page_icon="🎂",
    layout="wide"
)

# Initialize session state
if 'contacts' not in st.session_state:
    st.session_state.contacts = pd.DataFrame()
if 'selected_card' not in st.session_state:
    st.session_state.selected_card = None
if 'card_message' not in st.session_state:
    st.session_state.card_message = ""

def load_contacts_from_file(uploaded_file):
    """Load contacts from uploaded text file"""
    try:
        content = uploaded_file.read().decode('utf-8')
        lines = content.strip().split('\n')
        
        contacts = []
        for line in lines:
            if line.strip():
                parts = line.split(',')
                if len(parts) >= 3:
                    name = parts[0].strip()
                    address = parts[1].strip()
                    birthdate = parts[2].strip()
                    contacts.append({
                        'Name': name,
                        'Address': address,
                        'Birthdate': birthdate
                    })
        
        return pd.DataFrame(contacts)
    except Exception as e:
        st.error(f"Error loading file: {str(e)}")
        return pd.DataFrame()

def check_upcoming_birthdays(contacts_df, days_ahead=7):
    """Check for upcoming birthdays"""
    if contacts_df.empty:
        return pd.DataFrame()
    
    today = datetime.now()
    upcoming = []
    
    for _, contact in contacts_df.iterrows():
        try:
            # Parse birthdate (assuming MM/DD/YYYY or MM-DD-YYYY format)
            birth_str = contact['Birthdate'].replace('-', '/').replace('.', '/')
            birth_date = datetime.strptime(birth_str, '%m/%d/%Y')
            
            # Calculate this year's birthday
            this_year_birthday = birth_date.replace(year=today.year)
            
            # If birthday has passed this year, check next year
            if this_year_birthday < today:
                this_year_birthday = birth_date.replace(year=today.year + 1)
            
            days_until = (this_year_birthday - today).days
            
            if 0 <= days_until <= days_ahead:
                upcoming.append({
                    'Name': contact['Name'],
                    'Address': contact['Address'],
                    'Birthdate': contact['Birthdate'],
                    'Days Until': days_until,
                    'This Year Birthday': this_year_birthday.strftime('%m/%d/%Y')
                })
        except:
            continue
    
    return pd.DataFrame(upcoming)

def send_birthday_notification(recipient_email, birthday_person, smtp_config):
    """Send email notification about upcoming birthday"""
    try:
        msg = MIMEMultipart()
        msg['From'] = smtp_config['email']
        msg['To'] = recipient_email
        msg['Subject'] = f"🎂 Birthday Reminder: {birthday_person['Name']}"
        
        body = f"""
        Hi there!
        
        This is a reminder that {birthday_person['Name']}'s birthday is coming up in {birthday_person['Days Until']} day(s)!
        
        Birthday: {birthday_person['Birthdate']}
        Address: {birthday_person['Address']}
        
        Would you like to send them a birthday card?
        
        Visit your Birthday Card Manager app to select and send a card!
        
        Best regards,
        Birthday Card Manager
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(smtp_config['server'], smtp_config['port'])
        server.starttls()
        server.login(smtp_config['email'], smtp_config['password'])
        server.send_message(msg)
        server.quit()
        
        return True
    except Exception as e:
        st.error(f"Failed to send email: {str(e)}")
        return False

def create_birthday_card(card_type, message, recipient_name):
    """Create a birthday card image"""
    # Create a card image (400x300 pixels)
    width, height = 400, 300
    
    # Card templates with different colors
    templates = {
        "Classic": {"bg": "#FFE4E1", "text": "#8B0000"},
        "Modern": {"bg": "#E6E6FA", "text": "#4B0082"},
        "Fun": {"bg": "#FFB6C1", "text": "#FF1493"},
        "Elegant": {"bg": "#F0F8FF", "text": "#191970"}
    }
    
    template = templates.get(card_type, templates["Classic"])
    
    # Create image
    img = Image.new('RGB', (width, height), template["bg"])
    draw = ImageDraw.Draw(img)
    
    try:
        # Try to use a better font if available
        title_font = ImageFont.truetype("arial.ttf", 24)
        text_font = ImageFont.truetype("arial.ttf", 16)
    except:
        # Fallback to default font
        title_font = ImageFont.load_default()
        text_font = ImageFont.load_default()
    
    # Draw title
    title = f"Happy Birthday, {recipient_name}!"
    title_bbox = draw.textbbox((0, 0), title, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    title_x = (width - title_width) // 2
    draw.text((title_x, 50), title, fill=template["text"], font=title_font)
    
    # Draw message
    words = message.split()
    lines = []
    current_line = []
    
    for word in words:
        test_line = ' '.join(current_line + [word])
        test_bbox = draw.textbbox((0, 0), test_line, font=text_font)
        test_width = test_bbox[2] - test_bbox[0]
        
        if test_width <= width - 40:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
    
    if current_line:
        lines.append(' '.join(current_line))
    
    y_offset = 120
    for line in lines:
        line_bbox = draw.textbbox((0, 0), line, font=text_font)
        line_width = line_bbox[2] - line_bbox[0]
        line_x = (width - line_width) // 2
        draw.text((line_x, y_offset), line, fill=template["text"], font=text_font)
        y_offset += 25
    
    return img

def generate_usps_postage_link(address):
    """Generate a link to USPS postage printing"""
    # This creates a link to USPS Click-N-Ship
    base_url = "https://cns.usps.com/mailpieces"
    encoded_address = address.replace(' ', '%20').replace(',', '%2C')
    return f"{base_url}?destination={encoded_address}"

def main():
    st.title("🎂 Birthday Card Manager")
    st.markdown("Upload your contacts file and manage birthday card sending!")
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Email settings
        st.subheader("Email Notification Settings")
        email_enabled = st.checkbox("Enable Email Notifications")
        
        if email_enabled:
            notification_email = st.text_input("Your Email Address")
            smtp_server = st.text_input("SMTP Server", value="smtp.gmail.com")
            smtp_port = st.number_input("SMTP Port", value=587)
            smtp_email = st.text_input("SMTP Email")
            smtp_password = st.text_input("SMTP Password", type="password")
            
            smtp_config = {
                'server': smtp_server,
                'port': smtp_port,
                'email': smtp_email,
                'password': smtp_password
            }
        
        # Birthday check settings
        st.subheader("Birthday Check Settings")
        days_ahead = st.slider("Check birthdays how many days ahead?", 1, 30, 7)
    
    # Main interface
    tab1, tab2, tab3, tab4 = st.tabs(["📁 Upload Contacts", "🎂 Check Birthdays", "💌 Create Cards", "📮 Send Cards"])
    
    with tab1:
        st.header("Upload Contacts File")
        st.markdown("""
        Upload a text file with your contacts in this format:
        ```
        John Doe, 123 Main St, Anytown ST 12345, 03/15/1990
        Jane Smith, 456 Oak Ave, Another City ST 67890, 07/22/1985
        ```
        Format: Name, Address, Birthdate (MM/DD/YYYY)
        """)
        
        uploaded_file = st.file_uploader("Choose a text file", type=['txt'])
        
        if uploaded_file is not None:
            contacts_df = load_contacts_from_file(uploaded_file)
            st.session_state.contacts = contacts_df
            
            if not contacts_df.empty:
                st.success(f"Loaded {len(contacts_df)} contacts!")
                st.dataframe(contacts_df)
            else:
                st.error("No valid contacts found in the file.")
    
    with tab2:
        st.header("Upcoming Birthdays")
        
        if not st.session_state.contacts.empty:
            upcoming = check_upcoming_birthdays(st.session_state.contacts, days_ahead)
            
            if not upcoming.empty:
                st.success(f"Found {len(upcoming)} upcoming birthdays!")
                st.dataframe(upcoming)
                
                # Send notifications
                if email_enabled and notification_email and st.button("Send Email Notifications"):
                    for _, birthday in upcoming.iterrows():
                        if send_birthday_notification(notification_email, birthday, smtp_config):
                            st.success(f"Notification sent for {birthday['Name']}")
                        else:
                            st.error(f"Failed to send notification for {birthday['Name']}")
            else:
                st.info(f"No birthdays in the next {days_ahead} days.")
        else:
            st.warning("Please upload contacts first.")
    
    with tab3:
        st.header("Create Birthday Cards")
        
        if not st.session_state.contacts.empty:
            # Select recipient
            recipient = st.selectbox("Select Recipient", st.session_state.contacts['Name'].tolist())
            
            if recipient:
                col1, col2 = st.columns(2)
                
                with col1:
                    # Card options
                    st.subheader("Card Design")
                    card_type = st.selectbox("Choose Card Style", ["Classic", "Modern", "Fun", "Elegant"])
                    
                    # Custom message
                    st.subheader("Card Message")
                    default_messages = [
                        "Wishing you a wonderful birthday filled with happiness and joy!",
                        "Hope your special day brings you lots of joy and happiness!",
                        "Another year older, another year wiser. Happy Birthday!",
                        "May all your birthday wishes come true!"
                    ]
                    
                    suggested_message = st.selectbox("Choose a message", ["Custom"] + default_messages)
                    
                    if suggested_message == "Custom":
                        message = st.text_area("Write your custom message", height=100)
                    else:
                        message = suggested_message
                        st.text_area("Message preview", value=message, height=100, disabled=True)
                
                with col2:
                    if message:
                        # Preview card
                        st.subheader("Card Preview")
                        card_img = create_birthday_card(card_type, message, recipient)
                        st.image(card_img, caption=f"Birthday card for {recipient}")
                        
                        # Store in session state
                        st.session_state.selected_card = card_img
                        st.session_state.card_message = message
        else:
            st.warning("Please upload contacts first.")
    
    with tab4:
        st.header("Send/Print Cards")
        
        if st.session_state.selected_card is not None:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📱 Digital Options")
                
                # Download card
                buf = io.BytesIO()
                st.session_state.selected_card.save(buf, format='PNG')
                btn = st.download_button(
                    label="Download Card Image",
                    data=buf.getvalue(),
                    file_name=f"birthday_card_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
                    mime="image/png"
                )
                
                # Print instructions
                st.info("💡 **Printing Tips:**\n- Download the card image\n- Print on cardstock paper\n- Use high-quality color printing\n- Fold in half for a greeting card")
            
            with col2:
                st.subheader("📮 Mailing Options")
                
                # Get recipient address
                if not st.session_state.contacts.empty:
                    selected_contact = st.selectbox("Select recipient for mailing", st.session_state.contacts['Name'].tolist())
                    
                    if selected_contact:
                        contact_info = st.session_state.contacts[st.session_state.contacts['Name'] == selected_contact].iloc[0]
                        st.write(f"**Address:** {contact_info['Address']}")
                        
                        # USPS postage link
                        postage_link = generate_usps_postage_link(contact_info['Address'])
                        st.markdown(f"[🏷️ Print USPS Postage]({postage_link})")
                        
                        # Mailing service options
                        st.subheader("📦 Mailing Services")
                        st.markdown("""
                        **Options for sending your card:**
                        - **Print & Mail Yourself**: Download card, print, and mail
                        - **Online Card Services**: Upload to services like:
                          - Shutterfly
                          - Hallmark
                          - American Greetings
                          - Moonpig
                        - **USPS**: Use Click-N-Ship for postage
                        """)
        else:
            st.warning("Please create a card first in the 'Create Cards' tab.")

if __name__ == "__main__":
    main()