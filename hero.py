import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
from googletrans import Translator
import re
import subprocess
import concurrent.futures
import multiprocessing
import functools

translator = Translator()
translated_subtitles = []
thread_pool_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

def tk_after(target):
 
    @functools.wraps(target)
    def wrapper(self, *args, **kwargs):
        args = (self,) + args
        self.after(0, target, *args, **kwargs)
 
    return wrapper

def submit_to_pool_executor(executor):
    '''Decorates a method to be sumbited to the passed in executor'''
    def decorator(target):
 
        @functools.wraps(target)
        def wrapper(*args, **kwargs):
            result = executor.submit(target, *args, **kwargs)
            result.add_done_callback(executor_done_call_back)
            return result
 
        return wrapper
 
    return decorator

def executor_done_call_back(future):
    exception = future.exception()
    if exception:
        raise exception
 

def clean_subtitle_text(text):
        cleaned_text = re.sub(r'<.*?>', '', text)
        return cleaned_text
        
def translate_subtitle(args):
    subtitle, targetLanguage, progress_queue = args
    translator = Translator()
    lines = subtitle.strip().split('\n')
    if len(lines) >= 3:
        subtitle_number = lines[0]
        timestamp = lines[1]
        subtitle_text = '\n'.join(lines[2:])

        cleaned_text = clean_subtitle_text(subtitle_text)
        translated = translator.translate(cleaned_text, src='auto', dest=targetLanguage)
        translated_text = translated.text

        cleaned_translated_text = clean_subtitle_text(translated_text)
        encoded_translated_text = cleaned_translated_text.encode('utf-8')
        print(f'Progress => {subtitle_number}.')
        progress_queue.put(subtitle_number)

        return f'{subtitle_number}\n{timestamp}\n{encoded_translated_text.decode()}\n\n'
    else:
        return ''

class Hero:
    def __init__(self):
        self.subtitles = []
        self.fileName = ""
        # self.outputTextEdit = tk.Text()

    def translateSubtitles(self, targetLanguage, progress_var):
        if targetLanguage != "Select Target Language":
            translated_subtitles = []

            # Create a pool of worker processes
            # pool = multiprocessing.Pool()
            tot = len(self.subtitles)
            cur = 1
            import queue
            progress_queue = queue.Queue()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [executor.submit(translate_subtitle, (subtitle, targetLanguage, progress_queue)) for subtitle in self.subtitles]
                while len(translated_subtitles) < len(self.subtitles):
                    try:
                        subtitle_number = progress_queue.get(timeout=1)
                        progress_var.set(int(subtitle_number))
                    except queue.Empty:
                        pass
                for future in concurrent.futures.as_completed(futures):
                    print(future.result())
                    cur += 1
                    translated_subtitles.append(future.result())

            # pool.close()
            # pool.join()

            # Append the translated subtitles to the list
            # translated_subtitles.extend(results.get())

            with open('translated_subtitles.srt', 'w', encoding='utf-8') as f:
                f.writelines(translated_subtitles)

            # self.outputTextEdit.insert(tk.END, f'Translated subtitles to {targetLanguage} and saved as translated_subtitles.srt\n')


class SubtitleTranslator:
    def __init__(self, root):
        self.root = root
        self.root.title("Subtitle Translator")

        self.fileName = ""
        self.subtitles = []
        self.subtitle_language = ""
        # self.progress = ttk.Progressbar(orient="horizontal", length=200, mode="determinate")

        # Create and configure UI elements
        self.selectFileBtn = ttk.Button(root, text="Select Video File", command=self.selectFile)
        self.selectFileBtn.grid(row=0, column=0, padx=10, pady=10)

        self.videoNameLabel = ttk.Label(root, text="Selected Video: None")
        self.videoNameLabel.grid(row=0, column=1, padx=10, pady=10)

        self.subtitleTrackComboBox = ttk.Combobox(root, values=["Select Subtitle Track"])
        self.subtitleTrackComboBox.grid(row=1, column=0, padx=10, pady=10)

        self.targetLanguageComboBox = ttk.Combobox(root, values=["Select Target Language", "English", "French", "Spanish", "Hindi", "Telugu", "Tamil"])
        self.targetLanguageComboBox.grid(row=1, column=1, padx=10, pady=10)

        self.translateBtn = ttk.Button(root, text="Translate Subtitles", command=self.translateSubtitles)
        self.translateBtn.grid(row=2, column=0, padx=10, pady=10)

        self.addSubtitlesBtn = ttk.Button(root, text="Add Translated Subtitles to Video", command=self.addSubtitlesToVideo)
        self.addSubtitlesBtn.grid(row=2, column=1, padx=10, pady=10)

        self.outputTextEdit = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=40, height=10)
        self.outputTextEdit.grid(row=3, column=0, columnspan=2, padx=10, pady=10)
    
        self.progress = ttk.Progressbar(root, orient="horizontal", length=200, mode="determinate")
        self.progress.grid(row=4, column=0, columnspan=2, padx=10, pady=2)
        
        self.progress_label = tk.Label(root, text='0%')
        self.progress_label.grid(row=5, column=0, columnspan=2, padx=10, pady=2)
  

    def selectFile(self):
        fileName = filedialog.askopenfilename(title="Select Video File")
        if fileName:
            self.fileName = fileName
            self.videoNameLabel.config(text=f"Selected Video: {self.fileName}")
            self.loadSubtitleTracks()

    def loadSubtitleTracks(self):
        # Use FFprobe to get the subtitle tracks in the video file
        probe_result = subprocess.run([
            'ffprobe',
            '-v', 'error',
            '-select_streams', 's',
            '-show_entries', 'stream_tags=language,title',
            '-of', 'csv=p=0',
            self.fileName
        ], capture_output=True, text=True)
        print(probe_result)

        subtitle_tracks = probe_result.stdout.strip().split('\n')
        print(subtitle_tracks, 'seac')

        self.subtitleTrackComboBox['values'] = ["Select Subtitle Track"] + subtitle_tracks
        self.outputTextEdit.insert(tk.END, 'Subtitle tracks loaded.\n')

    def extractSubtitles(self):
        selected_track = self.subtitleTrackComboBox.get()

        if selected_track != "Select Subtitle Track":
            track_index = self.subtitleTrackComboBox.current()

            # Use FFmpeg to extract selected subtitle track and save as an SRT file
            output_subtitle = 'selected_subtitle.srt'

            subprocess.run([
                'ffmpeg',
                '-y',
                '-i', self.fileName,
                '-map', f'0:s:{track_index - 1}',
                output_subtitle
            ])
            print('searching for', track_index)
            # Read the extracted subtitles and store lines
            with open(output_subtitle, 'r', encoding='utf-8') as f:
                self.subtitles = f.read().split('\n\n')
                print(self.subtitles)

            self.outputTextEdit.insert(tk.END, f'Subtitle segments extracted from {selected_track}.\n')

    def clean_subtitle_text(self, text):
        # Remove <i> and </i> tags
        cleaned_text = re.sub(r'<.*?>', '', text)
        # print("after removed", cleaned_text)
        return text

    # Seperating blocking code with a child thread 
    @submit_to_pool_executor(thread_pool_executor)
    def translateSubtitles(self):
        self.extractSubtitles()
        targetLanguage = self.targetLanguageComboBox.get()
        if targetLanguage != "Select Target Language":
            import time
            start = time.time()
            bro = Hero()
            bro.fileName = self.fileName
            bro.subtitles = self.subtitles
            bro.subtitle_language = self.subtitleTrackComboBox.get()
            self.outputTextEdit.insert(tk.END, f'Translating subtitles to {targetLanguage}...\n')
            progress_var = tk.DoubleVar()
            progress_var.set(0)
            self.progress.config(variable=progress_var, maximum=len(self.subtitles))
            translated_subtitles = []
            tot = len(self.subtitles)
            cur = 1
            import queue
            progress_queue = queue.Queue()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [executor.submit(translate_subtitle, (subtitle, targetLanguage, progress_queue)) for subtitle in self.subtitles]
                for future in concurrent.futures.as_completed(futures):
                    try:
                        idx = int(future.result().split('\n')[0])
                        if progress_var.get() < idx:
                            progress_var.set(idx)
                            percentage = int((self.progress['value'] / self.progress['maximum']) * 100)
                            self.progress_label.config(text=f'{percentage}%')
                    except:
                        pass
                    translated_subtitles.append(future.result())
            # pool.join()

            # Append the translated subtitles to the list
            # translated_subtitles.extend(results.get())

            with open('translated_subtitles.srt', 'w', encoding='utf-8') as f:
                f.writelines(translated_subtitles)

            self.outputTextEdit.insert(tk.END, f'Translated subtitles to {targetLanguage} and saved as translated_subtitles.srt\n')
            end = time.time()
            print("Multi Threading finished in ", end - start)

            #  print(f'Progress => {i + 1} / {len(self.subtitles)}.')
            #         self.outputTextEdit.insert(tk.END, f'Progress => {i + 1} / {len(self.subtitles)}.\n')
            # for i , subtitle in enumerate(self.subtitles):
            #     lines = subtitle.strip().split('\n')
            #     if len(lines) >= 3:
            #         subtitle_number = lines[0]
            #         timestamp = lines[1]
            #         subtitle_text = '\n'.join(lines[2:])

            #         cleaned_text = self.clean_subtitle_text(subtitle_text)
            #         translated = translator.translate(cleaned_text, src='auto', dest=targetLanguage)
            #         translated_text = translated.text

            #         cleaned_translated_text = self.clean_subtitle_text(translated_text)
            #         encoded_translated_text = cleaned_translated_text.encode('utf-8')
            #         translated_subtitles.append(f'{subtitle_number}\n{timestamp}\n{encoded_translated_text.decode()}\n')
            #         translated_subtitles.append('\n')
            #         print(f'Progress => {i + 1} / {len(self.subtitles)}.')
            #         self.outputTextEdit.insert(tk.END, f'Progress => {i + 1} / {len(self.subtitles)}.\n')
                    # self.progress['value'] = progress_value
                    # self.progress.update()

            # with open('translated_subtitles.srt', 'w', encoding='utf-8') as f:
            #     f.writelines(translated_subtitles)

            # self.outputTextEdit.insert(tk.END, f'Translated subtitles to {targetLanguage} and saved as translated_subtitles.srt\n')

    def addSubtitlesToVideo(self):
        file_extension = self.fileName.split('.')[-1]
        output_video = f'output.{file_extension}'

        subprocess.run([
            'ffmpeg',
            '-i', self.fileName,
            '-i', 'translated_subtitles.srt',
            '-c', 'copy',
            '-scodec', 'srt',
            '-metadata:s:s:1', f'title={self.subtitle_language}',
            '-disposition:s:1', 'default',
            '-map', '0',
            '-map', '1',
            '-y', output_video
        ])

        self.outputTextEdit.insert(tk.END, f'Added translated subtitles to video and saved as {output_video}\n')


def main():
    root = tk.Tk()
    app = SubtitleTranslator(root)
    root.mainloop()

if __name__ == "__main__":
    main()
