import streamlit as st

from ai_generator import generate_topic_package, save_generated_content
from crm_newsletter import (
    get_campaign_overview,
    orchestrate_campaign,
    send_newsletter_to_contact,
)
from performance_analysis import analyze_performance

st.title("NovaMind AI Marketing Dashboard")

# 1️⃣ Generate marketing content
st.header("1. Generate Marketing Content")
topic = st.text_input("Enter your marketing topic:")

if st.button("Generate Content"):
    if not topic:
        st.warning("Please provide a topic before generating content.")
    else:
        with st.spinner("Generating outline, blog draft, and persona newsletters..."):
            package = generate_topic_package(topic)

        if package.get("error"):
            st.error(package["error"])
            raw_output = package.get("raw_output")
            if raw_output:
                st.code(raw_output, language="json")
        else:
            save_generated_content(topic, package)
            st.success("Content generated and saved to generated_content.json.")

            st.subheader("Blog Outline")
            outline = package.get("blog_outline", [])
            if outline:
                for idx, item in enumerate(outline, start=1):
                    st.write(f"{idx}. {item}")
            else:
                st.write("No outline returned.")

            st.subheader("Blog Draft (~400-600 words)")
            st.write(package.get("blog_draft", {}).get("content", "No draft returned."))

            st.subheader("Persona Newsletters")
            newsletters = package.get("newsletters", [])
            if newsletters:
                for letter in newsletters:
                    st.markdown(f"**{letter.get('persona', 'Persona')}**")
                    st.write(f"Subject: {letter.get('subject_line', 'N/A')}")
                    st.write(f"Preview: {letter.get('preview_text', 'N/A')}")
                    st.write(letter.get("body", "No body provided."))
                    st.divider()
            else:
                st.write("No newsletters returned.")


# 2️⃣ Send newsletter via Resend
st.header("2. Send Newsletter via Resend")
try:
    overview = get_campaign_overview()
    persona_choices = overview["personas"]
    blog_title = overview["blog_title"]
except Exception as exc:
    persona_choices = []
    blog_title = ""
    st.info("Generate and save content first to unlock sending.")

if persona_choices:
    st.caption(f"Current campaign: {blog_title}")
    st.write("Deliver persona-specific newsletters instantly using the Resend API.")
    with st.form("single_send_form"):
        email = st.text_input("Recipient email")
        first_name = st.text_input("First name (optional)")
        last_name = st.text_input("Last name (optional)")
        persona = st.selectbox("Persona segment", persona_choices)
        submitted = st.form_submit_button("Send Newsletter Now")

    if submitted:
        if not email:
            st.error("Recipient email is required.")
        else:
            try:
                result = send_newsletter_to_contact(
                    {
                        "email": email,
                        "first_name": first_name or "",
                        "last_name": last_name or "",
                        "persona": persona,
                    }
                )
                st.success(
                    f"Sent newsletter '{result['newsletter_id']}' to {result['email']} via Resend."
                )
            except Exception as exc:  # pylint: disable=broad-except
                st.error(f"Failed to send: {exc}")

    st.subheader("Bulk send to saved contacts")
    if st.button("Send to contact list"):
        with st.spinner("Sending newsletters to contacts..."):
            try:
                orchestrate_campaign()
                st.success("Bulk campaign completed via Resend. Check campaign_log.json for details.")
            except Exception as exc:  # pylint: disable=broad-except
                st.error(f"Bulk send failed: {exc}")


# 3️⃣ Performance analysis
st.header("3. View Performance Data & AI Insights")
if st.button("Analyze Performance"):
    summary, data = analyze_performance()
    st.json(data)
    st.subheader("AI Performance Summary")
    st.text(summary)
