import customtkinter as ctk
import threading
import sys
import os
from video_pipeline import VideoProcessor

# Theme settings
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")  # We will override colors to Orange manually

# Redirect print statements to the GUI textbox
class TextRedirector:
    def __init__(self, textbox):
        self.textbox = textbox

    def write(self, string):
        self.textbox.insert("end", string)
        self.textbox.see("end")  # Auto-scroll to bottom

    def flush(self):
        pass

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("🎬 Video Summarizer")
        self.geometry("900x650")
        
        # Processor instance
        self.processor = None
        
        # Grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # Title Label
        self.title_label = ctk.CTkLabel(self, text="Video Summarizer AI", font=ctk.CTkFont(size=24, weight="bold"), text_color="#ff7f00")
        self.title_label.grid(row=0, column=0, columnspan=2, padx=20, pady=(20, 10))

        # URL Input
        self.url_entry = ctk.CTkEntry(self, placeholder_text="🔗 Paste YouTube URL or Video File Path here...", width=600)
        self.url_entry.grid(row=1, column=0, columnspan=2, padx=20, pady=10)

        # Controls Frame
        self.controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.controls_frame.grid(row=2, column=0, columnspan=2, padx=20, pady=10)

        # Model Selection
        self.model_label = ctk.CTkLabel(self.controls_frame, text="Whisper Model:")
        self.model_label.pack(side="left", padx=(0, 10))
        self.model_var = ctk.StringVar(value="base")
        self.model_menu = ctk.CTkOptionMenu(self.controls_frame, values=["tiny", "base", "small", "medium", "large"], 
                                            variable=self.model_var, fg_color="#ff7f00", button_color="#cc6600", button_hover_color="#e67300")
        self.model_menu.pack(side="left", padx=10)
        
        # Caching Option
        self.cache_var = ctk.BooleanVar(value=True)
        self.cache_check = ctk.CTkCheckBox(self.controls_frame, text="Use Cache", variable=self.cache_var, 
                                           fg_color="#ff7f00", hover_color="#cc6600")
        self.cache_check.pack(side="left", padx=20)

        # Process Button
        self.process_btn = ctk.CTkButton(self.controls_frame, text="🚀 Process Video", command=self.start_processing, 
                                         fg_color="#ff7f00", hover_color="#cc6600", font=ctk.CTkFont(weight="bold"))
        self.process_btn.pack(side="left", padx=20)

        # Tab View for Logs and Results
        self.tabview = ctk.CTkTabview(self, segmented_button_selected_color="#ff7f00", segmented_button_selected_hover_color="#cc6600")
        self.tabview.grid(row=3, column=0, columnspan=2, padx=20, pady=20, sticky="nsew")
        
        self.tabview.add("Terminal Logs")
        self.tabview.add("Summary")
        self.tabview.add("Timestamps")
        
        # Logs Textbox
        self.log_box = ctk.CTkTextbox(self.tabview.tab("Terminal Logs"), font=ctk.CTkFont(family="Consolas", size=12))
        self.log_box.pack(expand=True, fill="both", padx=10, pady=10)
        
        # Summary Textbox
        self.summary_box = ctk.CTkTextbox(self.tabview.tab("Summary"), font=ctk.CTkFont(size=14))
        self.summary_box.pack(expand=True, fill="both", padx=10, pady=10)
        
        # Timestamps Textbox
        self.ts_box = ctk.CTkTextbox(self.tabview.tab("Timestamps"), font=ctk.CTkFont(size=14))
        self.ts_box.pack(expand=True, fill="both", padx=10, pady=10)

        # Redirect terminal output to GUI
        sys.stdout = TextRedirector(self.log_box)
        sys.stderr = TextRedirector(self.log_box)

    def start_processing(self):
        url = self.url_entry.get().strip()
        if not url:
            self.log_box.insert("end", "\n[!] Please enter a valid URL or file path.\n")
            return
        
        # Disable button during processing
        self.process_btn.configure(state="disabled", text="⏳ Processing...")
        self.tabview.set("Terminal Logs")
        self.log_box.delete("1.0", "end")
        self.summary_box.delete("1.0", "end")
        self.ts_box.delete("1.0", "end")
        
        # Run processing in a separate thread so GUI doesn't freeze
        threading.Thread(target=self.process_video_thread, args=(url,), daemon=True).start()

    def process_video_thread(self, url):
        try:
            model = self.model_var.get()
            use_cache = self.cache_var.get()
            
            # Load processor if not loaded or if model changed
            if getattr(self, "processor_model", None) != model:
                print(f"Loading/Switching to {model} model...")
                self.processor = VideoProcessor(whisper_model=model)
                self.processor_model = model
                
            print(f"\nStarting pipeline for: {url}")
            
            results = self.processor.process_video(
                video_source=url,
                output_dir="output",
                max_summary_length=150,
                use_cache=use_cache
            )
            
            # Read files and populate UI tabs
            if os.path.exists(results["summary"]):
                with open(results["summary"], "r", encoding="utf-8") as f:
                    self.summary_box.insert("end", f.read())
            
            if os.path.exists(results["timestamps"]):
                with open(results["timestamps"], "r", encoding="utf-8") as f:
                    self.ts_box.insert("end", f.read())
            
            print("\n✅ Processing Complete! Check Summary and Timestamps tabs.")
            self.tabview.set("Summary")
            
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            
        finally:
            # Re-enable button
            self.process_btn.configure(state="normal", text="🚀 Process Video")

if __name__ == "__main__":
    app = App()
    app.mainloop()
