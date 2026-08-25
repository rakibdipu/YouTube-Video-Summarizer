import streamlit as st
import os
import time
from video_pipeline import VideoProcessor

# Page configuration
st.set_page_config(page_title="Video Summarizer", page_icon="🎬", layout="wide")

st.title("🎬 Video Summarizer")
st.markdown("Download, Transcribe, and Summarize videos with AI.")

# Initialize the processor in session state so it doesn't reload on every UI click
if "processor" not in st.session_state:
    st.session_state.processor = None

# Sidebar for settings
with st.sidebar:
    st.header("⚙️ Settings")
    whisper_model = st.selectbox("Whisper Model", ["tiny", "base", "small", "medium", "large"], index=1, 
                                 help="Base is a good balance. Use Small/Medium for better accuracy.")
    language = st.text_input("Language Code (Optional)", placeholder="e.g. en, es, bn", help="Leave blank for auto-detect")
    max_length = st.slider("Max Summary Length", min_value=50, max_value=300, value=150, step=10)
    use_cache = st.checkbox("Use Caching", value=True, help="Skip downloading/transcribing if already done before")
    
    if st.button("Load/Change Model", use_container_width=True):
        with st.spinner(f"Loading {whisper_model} model..."):
            st.session_state.processor = VideoProcessor(whisper_model=whisper_model)
            st.success("Model Loaded!")

# Main interface
url_input = st.text_input("🔗 Enter YouTube URL or local file path:")

if st.button("🚀 Process Video", type="primary", use_container_width=True):
    if not url_input:
        st.warning("Please enter a valid URL or path.")
    else:
        if st.session_state.processor is None:
            with st.spinner("Initializing AI Models... (First run takes time)"):
                st.session_state.processor = VideoProcessor(whisper_model=whisper_model)
        
        try:
            with st.spinner("Processing video... This may take a while depending on the video length."):
                lang_code = language.strip() if language.strip() else None
                
                # Run pipeline
                results = st.session_state.processor.process_video(
                    video_source=url_input,
                    output_dir="output",
                    language=lang_code,
                    max_summary_length=max_length,
                    use_cache=use_cache
                )
            
            st.success("✅ Processing Complete!")
            
            # Show Results in Tabs
            tab1, tab2, tab3, tab4 = st.tabs(["📝 Summary", "⏱️ Timestamps", "📜 Transcript", "📊 Metadata"])
            
            with tab1:
                st.subheader("Abstractive Summary & Key Points")
                with open(results["summary"], "r", encoding="utf-8") as f:
                    summary_text = f.read()
                st.markdown(summary_text)
                
                # Download button
                with open(results["markdown"], "r", encoding="utf-8") as f:
                    md_text = f.read()
                st.download_button("💾 Download Full Markdown Report", data=md_text, file_name="summary_report.md", mime="text/markdown")
                
            with tab2:
                st.subheader("Timestamped Transcript")
                if results["timestamps"]:
                    with open(results["timestamps"], "r", encoding="utf-8") as f:
                        ts_text = f.read()
                    st.text_area("Timestamps", ts_text, height=400, label_visibility="collapsed")
                else:
                    st.info("No timestamps available.")
                    
            with tab3:
                st.subheader("Raw Transcript")
                with open(results["transcript"], "r", encoding="utf-8") as f:
                    raw_text = f.read()
                st.text_area("Transcript", raw_text, height=400, label_visibility="collapsed")
                
            with tab4:
                st.subheader("Processing Stats")
                stats = results["stats"]
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Language", stats["language"].upper())
                col2.metric("Word Count", stats["word_count"])
                col3.metric("Summary Length", stats["summary_length"])
                col4.metric("Compression", f"{stats['compression']:.1f}%")
                
                if stats.get("cached"):
                    st.info("💡 Note: Loaded from cache.")
                
        except Exception as e:
            st.error(f"An error occurred: {e}")

