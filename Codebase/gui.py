import tkinter as tk
import iomanager
import numpy
from PIL import ImageTk, Image
import configparser
import subprocess
import os
import cv2
import time
import math
import datetime
from threading import Timer, Thread
from queue import Queue
import videoproc
import graphing as graph
# MatPlotLib imports
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("TkAgg")

# Load a tk window and widthdraw to allow images to be loaded
load = tk.Tk()
load.withdraw()

# Global variable to store app instance
app = None
# Function to show the GUI
def show_window():
    # Create a new app instance
    global app
    app = App()

# - APP ITEMS
class App(tk.Tk):
    # Variables
    video_page = None
    data_page = None
    settings_page = None
    status_bar = None
    theme_manager = None
    mouse_data = []

    # Constructor
    def __init__(self, *args, **kwargs):
        # Call superclass function
        tk.Toplevel.__init__(self, *args, **kwargs)
        # Create new theme manager
        self.theme_manager = ThemeManager(self)
        self.theme_manager.register_item("bgr", self)
        # Configure resizing options through grid
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        self.grid_columnconfigure(0, weight=1)
        # Configure appearance
        self.title("MouseHUB")
        if os.name == "nt":
            self.iconbitmap("../Assets/IconLarge.ico")
        else:
            self.iconbitmap("@../Assets/IconLarge.xbm")
        self.geometry("1280x720")
        self.minsize(780, 520)
        # Create frame view
        page_view = AppPageView(self, self.theme_manager)
        self.video_page = page_view.add_page(VideoPage)
        self.data_page = page_view.add_page(DataPage)
        self.settings_page = page_view.add_page(SettingsPage)
        # Create toolbar
        toolbar = AppToolbar(self)
        toolbar.add_button("Video", self.video_page.tkraise).set_active(True)
        toolbar.add_button("Data", self.data_page.tkraise)
        toolbar.add_button("Settings", self.settings_page.tkraise)
        toolbar.add_button("Exit", self.close)
        # Create status bar
        self.status_bar = AppStatusBar(self, "Copyright: \xa9 MouseHUB 2020.", self.theme_manager)
        # Show the first frame
        self.video_page.tkraise()
        # Apply the theme manager colours
        self.theme_manager.apply_last_theme()
        # Register window close event
        self.protocol("WM_DELETE_WINDOW", self.close)
        # Start the main app loop
        self.mainloop()

    # Function to close the window
    def close(self):
        # Stop any video if playing
        if (self.video_page.video_player.playing):
            self.video_page.video_player.stop()
        # Destroy the tkinter window
        self.destroy()
        # Stop the application
        raise SystemExit

# - PAGE ITEMS
class VideoPage(tk.Frame):
    # Variables
    video_queue = None
    process_index = 0
    process_total = 0

    # Constructor
    def __init__(self, parent):
        # Bind parent
        self.parent = parent.app
        # Call superclass function
        tk.Frame.__init__(self, parent)
        parent.app.theme_manager.register_item("bgr", self)
        self.grid(row=0, column=0, sticky="nesw")
        # Load images
        button_add = ImageTk.PhotoImage(file="../Assets/ButtonAdd.png")
        button_clear = ImageTk.PhotoImage(file="../Assets/ButtonClear.png")
        button_process = ImageTk.PhotoImage(file="../Assets/ButtonProcess.png")
        # Configure resizing
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        # Videos List
        queue_container = tk.Frame(self)
        queue_container.grid(row=0, column=0, sticky="nesw")
        queue_container.grid_rowconfigure(0, weight=0)
        queue_container.grid_rowconfigure(1, weight=1)
        queue_container.grid_columnconfigure(0, weight=1)
        parent.app.theme_manager.register_item("bgr", queue_container)
        # Queue buttons
        queue_buttons_frame = tk.Frame(queue_container)
        queue_buttons_frame.grid(row=0, column=0, sticky="nesw", pady=(0, 4))
        parent.app.theme_manager.register_item("ctr", queue_buttons_frame)
        # Add buttons
        IconButton(queue_buttons_frame, button_add, self.import_videos, parent.app.theme_manager).grid(row=0, column=0, padx=4, pady=4)
        IconButton(queue_buttons_frame, button_clear, self.clear_videos, parent.app.theme_manager).grid(row=0, column=1, padx=4, pady=4)
        IconButton(queue_buttons_frame, button_process, self.process_videos, parent.app.theme_manager).grid(row=0, column=2, padx=4, pady=4)
        # Video player
        self.video_player = VideoPlayer(self, parent.app.theme_manager)
        self.video_player.grid(row=0, column=1, padx=(4, 0), sticky="nesw")
        # Queue items list
        self.video_queue = VideoQueue(queue_container, parent.app.theme_manager, self.video_player)
        self.video_queue.grid(row=1, column=0, sticky="nesw")

    # Function to allow the user to select and import videos
    def import_videos(self):
        videos = iomanager.get_videos(True)
        self.video_queue.add_videos(videos)

    # Function to clear the user selected videos
    def clear_videos(self):
        # Remove all videos from queue
        self.video_queue.clear_videos()
        # Check if the player is playing
        if (self.video_player.playing):
            self.video_player.stop()
        # Delete all from video player canvas
        self.video_player.canvas.delete("all")
        self.video_player.frame = None
        self.video_player.controls_trackbar.reset()

    # Function to process the user selected videos
    def process_videos(self):
        # Get videos from video_queue
        videos = self.video_queue.get_videos()
        # Get config setting for output path
        self.config = configparser.ConfigParser()
        self.config.read("config.ini")
        output_location = self.config.get("General", "outputPath")
        generate_bounded_video = True if self.config.get("Video", "generate_video") == "1" else False
        # Create new thread
        thread = Thread(target=self._process_videos, daemon=True, args=[videos, generate_bounded_video, output_location])
        thread.start()

    # Private function to process videos on a separate thread
    def _process_videos(self, videos, generate_bounded_video, output_location):
        # Counter for video being processed
        self.processing_index = 1
        self.processing_total = len(videos)
        # Process all videos and append output to mouseData
        for video in videos:
            # Update status
            self.parent.status_bar.set_status("Processing video " + str(self.processing_index) + " of " + str(self.processing_total))
            # Start processing video
            self.parent.mouse_data.append(videoproc.process_video(video.file, generate_bounded_video, output_location, self._progress_update))
            # Increment processing counter
            self.processing_index += 1
        self.parent.status_bar.set_status("Ready to process.")

    # Function to update the progress of the tracker
    def _progress_update(self, percentage):
        # Set processing status
        self.parent.status_bar.set_status("Processing video " + str(self.processing_index) + " of " + str(self.processing_total) + " (" + "{:.1f}".format(percentage) + "%)")

class DataPage(tk.Frame):
    def __init__(self, parent):
        # Set theme manager
        self.theme_manager = parent.app.theme_manager

        # Call superclass function
        tk.Frame.__init__(self, parent)
        self.grid(row=0, column=0, sticky="nesw")
        self.theme_manager.register_item("bgr", self)

        # Create graph figure and generator
        graph_figure = plt.figure() # Figure for graphing.
        graph_generator = graph.DataGraph() # object to store datagraph in.

        # Create warning label
        self.warning_label = tk.Label(self, text = "Warning!", font = ("Rockwell",25))
        self.theme_manager.register_item("bgr", self.warning_label)
        self.theme_manager.register_item("txt", self.warning_label)
        self.warning_label.grid(row=0, column=2, sticky='nesw',padx=10,pady=5)

        # Create warning text
        self.warning_text = tk.Label(self, text = "No videos have been processed yet!\nDisplayed data is placeholder until then.", font = ("Rockwell",15))
        self.theme_manager.register_item("bgr", self.warning_text)
        self.theme_manager.register_item("txt", self.warning_text)
        self.warning_text.grid(row=1, column=2, sticky='nesw',padx=10,pady=5)

        # Stacked bar graph button
        stack_bar_button = tk.Button(self, text = "Actogram Equivalent", font = ("Rockwell", 15), command=lambda: self.set_graph_bar_stacked(parent.app.mouse_data, graph_generator, graph_figure, self.my_plot))
        self.theme_manager.register_item("bgr", stack_bar_button)
        self.theme_manager.register_item("txt", stack_bar_button)
        stack_bar_button.grid(row=5, column=6, sticky='nesw',padx=50,pady=10)

        # Path graph button
        path_graph_button = tk.Button(self, text = "Line Graph", font = ("Rockwell", 15), command=lambda: self.set_graph_line(parent.app.mouse_data, graph_generator, graph_figure, self.my_plot))
        self.theme_manager.register_item("bgr", path_graph_button)
        self.theme_manager.register_item("txt", path_graph_button)
        path_graph_button.grid(row=6, column=6, sticky='n',padx=50,pady=10)

        # Placeholder data
        x_labels = {"Sleeping":0,"Eating":1,"Moving":2,"Undefined":3}
        y_values = [50,30,120,25]

        big_num = 300
        new_list = []

        # Iterate and populate with data
        for num in range(0,big_num):
                if num <= big_num/5:
                    new_list.append(0)
                elif num >= (big_num/5)*4:
                    new_list.append(0)
                elif num > big_num/5 and num < big_num/7*2:
                    new_list.append(2)
                else:
                    new_list.append(3)

        # Create list of co-ordinates
        coords = [[100,50],[110,60],[100,70],[90,80],[90,90],[80,90],[70,80],[80,90],[90,100],[100,110]]

        # Create position chart and display
        self.graph_figure, self.my_plot = graph_generator.create_position_chart(graph_figure, coords, 640, 480)

        # Title entry field
        title_entry = tk.Entry(self)
        self.theme_manager.register_item("bgr", title_entry)
        self.theme_manager.register_item("txt", title_entry)
        title_entry.grid(row = 2, column = 2, sticky = "nesw", padx = 50, pady = 5)

        # Set title button
        set_button = tk.Button(self, text="Set Title", command=lambda: self.set_title(title_entry, self.my_plot))
        self.theme_manager.register_item("bgr", set_button)
        self.theme_manager.register_item("txt", set_button)
        set_button.grid(row = 2, column = 3, sticky = "nesw", padx = 5, pady = 5)

        # Register theme change callback
        self.theme_manager.register_callback(self.on_theme_change)

        # Create and draw canvas
        self.canvas = FigureCanvasTkAgg(self.graph_figure, self)
        self.canvas.draw()
        # Configure in tkinter display
        self.canvas.get_tk_widget().grid(row=3, column=2, rowspan=99)

    def on_theme_change(self, theme):
        # Update graph figure
        self.graph_figure.set_facecolor(theme.background())
        # Update plot
        self.my_plot.tick_params(labelcolor=theme.text(), color=theme.container())
        self.my_plot.set_facecolor(theme.container())
        # Update plot spines
        for spine in self.my_plot.spines.values():
            spine.set_edgecolor(theme.container())
        # Update axes
        self.my_plot.set_xlabel("Time (s)", color=theme.text())
        self.my_plot.set_ylabel("Activity per Division", color=theme.text())
        # Update title color
        self.my_plot.set_title(self.my_plot.get_title(), color=theme.text())
        # Redraw
        self.canvas.draw()

    def set_title(self, title_entry, my_plot):
        # Update title
        my_plot.set_title(title_entry.get(), color=self.theme_manager.get_current_theme().text())
        # Redraw
        self.canvas.draw()

    def set_graph_bar(self, mouse_data, graph_generator, graph_figure, my_plot):
        # Create position chart
        graph_figure, my_plot = graph_generator.create_position_chart(graph_figure, coordsXY, 640, 480)
        # Draw canvas
        self.canvas.draw()

    def set_graph_bar_stacked(self, mouse_data, graph_generator, graph_figure, my_plot):
        # Check there is data to display
        if len(mouse_data) >= 1:
            # Clear plot
            my_plot.clear()
            # Remove warning labels
            self.warning_label.grid_forget()
            self.warning_text.grid_forget()

            # Create lists to store data
            mouse_pos = []
            mouse_width = []
            mouse_height = []

            # Iterate and append all data
            for data in mouse_data:
                for item in data:
                    mouse_pos.append([item[0][0],item[0][1]])
                    mouse_width.append(item[1])
                    mouse_height.append(item[2])

            # Estimate poses and store in variables
            position_meaning, position_list = graph_generator.estimate_poses_default(mouse_width, mouse_height, mouse_pos, 640, 480)

            # Create bar graph and update plot and graph figure
            self.graph_figure, self.my_plot = graph_generator.create_stacked_bar_chart(graph_figure, 0.33333333333, 5, position_meaning, position_list)

            # Set axes labels
            self.my_plot.set_xlabel("Frames")
            self.my_plot.set_ylabel("Activity Per Time Division")
            # Redraw canvas
            self.canvas.draw()

    def set_graph_line(self, mouse_data, graph_generator, graph_figure, my_plot):
        # Check there is data to display
        if len(mouse_data) >= 1:
            # Clear preivous plot
            my_plot.clear()
            # Clear warning labels
            self.warning_label.grid_forget()
            self.warning_text.grid_forget()

            # Variables to store mouse data
            mouse_pos = []
            mouse_width = []
            mouse_height = []

            # Iterate and append all data
            for data in mouse_data:
                for item in data:
                    mouse_pos.append([item[0][0],item[0][1]])
                    mouse_width.append(item[1])
                    mouse_height.append(item[2])

            # Generate position chart and update plot and graph figure
            self.graph_figure, self.my_plot = graph_generator.create_position_chart(graph_figure, mouse_pos, 640, 480)

            # Update axes labels
            self.my_plot.set_xlabel("X Position")
            self.my_plot.set_ylabel("Y Position")
            # Redraw graph
            self.canvas.draw()

class SettingsPage(tk.Frame):
    # Hashmaps to lookup values for settings
    lookup_boolean = {
        0: "1",
        1: "0"
    }
    lookup_theme = {
        1: "Light",
        2: "Dark",
        3: "Debug"
    }
    lookup_buffer = {
        1: "16",
        2: "32",
        3: "64",
        4: "128"
    }

    def __init__(self, parent):
        # Bind theme manager instance
        self.theme_manager = parent.app.theme_manager

        tk.Frame.__init__(self, parent)
        self.grid(row=0, column=0, sticky="nesw")
        parent.app.theme_manager.register_item("bgr", self)
        # Configuring rows
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(2, weight=1)

        # Load images for use in settings page
        self.yes = ImageTk.PhotoImage(file="../Assets/ButtonYesGr.png")
        self.no = ImageTk.PhotoImage(file="../Assets/ButtonNoRed.png")
        self.open = ImageTk.PhotoImage(file="../Assets/ButtonOpen.png")
        self.path = ImageTk.PhotoImage(file="../Assets/ButtonPath.png")
        no_select = ImageTk.PhotoImage(file="../Assets/ButtonNoSelect.png")
        select = ImageTk.PhotoImage(file="../Assets/ButtonSelect.png")

        # Create config parser
        self.config = configparser.ConfigParser()
        self.config.read("config.ini")
        output_location = self.config.get('General', 'OutputPath')

        # Creating a frame to put all the buttons in.
        settings_frame = tk.Frame(self)
        settings_frame.grid(row=0,column=1,sticky="nesw")
        parent.app.theme_manager.register_item("bgr", settings_frame)
        self.tkvar = tk.StringVar(load)
        # General Settings
        general_label = tk.Label(self, text="General Settings", font=("Rockwell",20))
        parent.app.theme_manager.register_item("bgr", general_label)
        parent.app.theme_manager.register_item("txt", general_label)
        general_label.grid(row=0,column=0,sticky="w",pady=10,padx=10)
        # Change Directory / Open Output Location
        self.output_location_label = tk.Label(self,text="Output Directory - " + output_location, font=("Rockwell",13))
        parent.app.theme_manager.register_item("bgr", self.output_location_label)
        parent.app.theme_manager.register_item("txt", self.output_location_label)
        self.output_location_label.grid(row=1,column=0,sticky="w",padx=10)
        # Output button
        output_button = tk.Button(self, command=self.set_directory, image=self.path, compound="left", highlightthickness=0, bd=0)
        parent.app.theme_manager.register_item("bgr", output_button)
        parent.app.theme_manager.register_item("hbgr", output_button)
        parent.app.theme_manager.register_item("abgr", output_button)
        output_button.grid(row=2,column=0,sticky="w",padx=10)
        # Open button
        open_button = tk.Button(self, command=self.open_path, image=self.open, compound="left", highlightthickness=0, bd=0)
        parent.app.theme_manager.register_item("bgr", open_button)
        parent.app.theme_manager.register_item("hbgr", open_button)
        parent.app.theme_manager.register_item("abgr", open_button)
        open_button.grid(row=2,column=0,sticky="w", padx=120)
        # Theme label
        theme_label= tk.Label(self, text="Client Theme", font=("Rockwell",16))
        parent.app.theme_manager.register_item("bgr", theme_label)
        parent.app.theme_manager.register_item("txt", theme_label)
        theme_label.grid(row=3, column=0, sticky='w',padx=10,pady=10)
        # Create buttons for themes
        self.ti = tk.IntVar()
        self.TB1 = RadioButton(self,parent.app.theme_manager,"Light",no_select,select,self.theme_save,self.ti,1)
        self.TB1.grid(row =4, column=0, sticky='w',padx=10)
        self.TB3 = RadioButton(self,parent.app.theme_manager,"Dark",no_select,select,self.theme_save,self.ti,2)
        self.TB3.grid(row=4, column=0, sticky='w', padx=110)
        self.TB4 = RadioButton(self,parent.app.theme_manager,"Debug",no_select,select,self.theme_save,self.ti,3)
        self.TB4.grid(row=4, column=0, sticky='w', padx=210)
        # Video Settings
        video_label = tk.Label(self, text="Video Settings", font=("Rockwell",20))
        parent.app.theme_manager.register_item("bgr", video_label)
        parent.app.theme_manager.register_item("txt", video_label)
        video_label.grid(row=5,column=0,sticky="w",pady=10,padx=10)
        # Save video label
        save_label = tk.Label(self, text="Generate Bounding Box Video File", font=("Rockwell",16))
        parent.app.theme_manager.register_item("bgr", save_label)
        parent.app.theme_manager.register_item("txt", save_label)
        save_label.grid(row=6, column=0, sticky='w',padx=10,pady=10)
        # Save video value
        self.svb = tk.IntVar()
        self.LB1 = CheckButton(self, parent.app.theme_manager,self.yes,self.no,self.generate_video, self.svb)
        self.LB1.grid(row=7,column=0,sticky="w",padx=10)
        # Playback buffer size
        bounding_box_label = tk.Label(self, text="Playback Buffer Size", font=("Rockwell",16))
        parent.app.theme_manager.register_item("bgr", bounding_box_label)
        parent.app.theme_manager.register_item("txt", bounding_box_label)
        bounding_box_label.grid(row=12,column=0,sticky='w',padx=10,pady=10)
        # Playback Buzzer Size RadioButton
        self.bs = tk.IntVar()
        self.LB6 = RadioButton(self,parent.app.theme_manager,"16",no_select,select,self.buffer_size,self.bs,1)
        self.LB6.grid(row=13, column=0,sticky="w",padx=10)
        self.LB7 = RadioButton(self,parent.app.theme_manager,"32",no_select,select,self.buffer_size,self.bs,2)
        self.LB7.grid(row=13, column=0,sticky="w",padx=110)
        self.LB8 = RadioButton(self,parent.app.theme_manager,"64",no_select,select,self.buffer_size,self.bs,3)
        self.LB8.grid(row=13, column=0,sticky="w",padx=210)
        self.LB9 = RadioButton(self,parent.app.theme_manager,"128",no_select,select,self.buffer_size,self.bs,4)
        self.LB9.grid(row=13, column=0,sticky="w",padx=310)
        # Data Settings
        data = tk.Label(self, text="Data Settings", font=("Rockwell",20), pady=20)
        parent.app.theme_manager.register_item("bgr", data)
        parent.app.theme_manager.register_item("txt", data)
        data.grid(row=0,column=1,sticky="w")
        # Mouse Tracking Setting
        mouse_tracking_label = tk.Label(self, text="Mouse Position", font=("Rockwell",16))
        parent.app.theme_manager.register_item("bgr", mouse_tracking_label)
        parent.app.theme_manager.register_item("txt", mouse_tracking_label)
        mouse_tracking_label.grid(row=1,column=1, sticky="w", pady=10)
        # Mouse tracking value
        self.mti = tk.IntVar()
        self.RB1 = CheckButton(self, parent.app.theme_manager, self.yes, self.no, self.mouse_tracking, self.mti)
        self.RB1.grid(row=2,column=1, sticky="w")
        # Pose Estimations/Mouse Behaviour
        mouse_behaviour_label = tk.Label(self, text="Mouse Behaviour", font=("Rockwell",16))
        parent.app.theme_manager.register_item("bgr", mouse_behaviour_label)
        parent.app.theme_manager.register_item("txt", mouse_behaviour_label)
        mouse_behaviour_label.grid(row=3,column=1, sticky="w",pady=10)
        # Mouse behaviour value
        self.mbi = tk.IntVar()
        self.RB2 = CheckButton(self, parent.app.theme_manager, self.yes, self.no, self.mouse_behaviour, self.mbi)
        self.RB2.grid(row=4,column=1, sticky="w")

        # Toggle all buttons
        self.togglebuttons()

    # Set Saved Video Directory and Display Label
    def set_directory(self):
        # Prompt for the directory
        output_location = tk.filedialog.askdirectory()
        if not (output_location == ""):
            self.config.read("config.ini")
            self.config.set("General", "OutputPath", output_location)
            with open('config.ini', 'w') as f:
                self.config.write(f)
            self.output_location_label.config(text="Output Location: " + output_location)

    # Set the Generate Video config
    def generate_video(self):
        self.config.read("config.ini")
        # Get the variable value
        v = self.svb.get()
        self.config.set("Video", "Generate_Video", self.lookup_boolean[v])
        with open('config.ini', 'w') as f:
            self.config.write(f)

    #Opens file path
    def open_path(self):
        self.config.read("config.ini")
        output = self.config.get("General", "OutputPath")
        subprocess.Popen(f'explorer {os.path.realpath(output)}')

    #Changes config for playback buffer size
    def buffer_size(self):
        self.config.read("config.ini")
        # Get variable valye
        bs = self.bs.get()
        self.config.set("Video", "Buffer_Size", self.lookup_buffer[bs])
        with open('config.ini', 'w') as f:
            self.config.write(f)

    #Changes config for mouse location tracking
    def mouse_tracking(self):
        self.config.read("config.ini")
        # Get variable value
        v = self.mti.get()
        self.config.set("Data", "Tracking_Data", self.lookup_boolean[v])
        with open('config.ini', 'w') as f:
            self.config.write(f)

    #Changes config for post estimation
    def mouse_behaviour(self):
        self.config.read("config.ini")
        # Get variable value
        v = self.mbi.get()
        self.config.set("Data", "Behaviour_Data", self.lookup_boolean[v])
        with open('config.ini', 'w') as f:
            self.config.write(f)

    def theme_save(self):
        self.config.read("config.ini")
        # Get variable valye
        v = self.ti.get()
        self.config.set("General", "Theme", self.lookup_theme[v])
        with open('config.ini', 'w') as f:
            self.config.write(f)
        # Apply the new theme
        self.theme_manager.apply_theme_name(self.lookup_theme[v])

    def togglebuttons(self):
        # Get output location
        output_location = self.config.get('General', 'OutputPath')
        # Check if the paath doesn't exist
        if not os.path.exists(output_location):
            self.config.set("General", "OutputPath", 'No Valid File Path Detected')
            with open('config.ini', 'w') as f:
                self.config.write(f)
            self.output_location_label.config(text="Output Location: " + output_location)
        # Tracking data
        v = self.config.get('Data', 'tracking_data')
        if v == '0':
            self.RB1.select()
        # Behaviour data
        v = self.config.get('Data', 'behaviour_data')
        if v == '0':
            self.RB2.select()
        # Bounding box data
        v = self.config.get('Video', 'bounding_box')
        if v == '0':
            self.LB5.select()
        # Theme data
        v = self.config.get('General', 'Theme')
        if v == "Light":
            self.TB1.select()
        elif v == "Dark":
            self.TB3.select()
        elif v == "Debug":
            self.TB4.select()
        # Buffer size data
        v = self.config.get('Video', 'buffer_size')
        if v == "16":
            self.LB6.select()
        elif v == "32":
            self.LB7.select()
        elif v == "64":
            self.LB8.select()
        elif v == "128":
            self.LB9.select()

# - BUTTON ITEMS
class MenuButton(tk.Button):
    active = False
    theme_manager = None

    def __init__(self, parent, text, func, theme_manager):
        # Load and store images
        self.tab = ImageTk.PhotoImage(file="../Assets/Tab.png")
        self.tab_active = ImageTk.PhotoImage(file="../Assets/TabActive.png")

        # Constructor call
        tk.Button.__init__(self, parent, image=self.tab, text=text, compound="center", command=func, bd=0, font=("Rockwell", 16), pady=0, highlightthickness=0)

        # Configure theme manager colours
        theme_manager.register_item("ctr", self)
        theme_manager.register_item("actr", self)
        theme_manager.register_item("txt", self)

        # Register events
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)

    def on_enter(self, event):
        if (not self.active):
            self.configure(image=self.tab_active)

    def on_leave(self, event):
        if (not self.active):
            self.configure(image=self.tab)

    def set_active(self, state):
        self.active = state
        if (self.active):
            self.configure(image=self.tab_active)
        else:
            self.configure(image=self.tab)

class IconButton(tk.Button):
    def __init__(self, parent, image, func, theme_manager):
        tk.Button.__init__(self, parent, image=image, compound="left", command=func, bd=0, padx=8, highlightthickness=0)
        theme_manager.register_item("ctr", self)
        theme_manager.register_item("actr", self)
        self.image = image

class CheckButton(tk.Checkbutton):
    def __init__(self,parent,theme_manager,image,image1,func,var):
        tk.Checkbutton.__init__(self,parent,image=image,variable=var,selectimage=image1, compound="left", command=func, bd=0, highlightthickness=0, indicatoron=0)
        theme_manager.register_item("bgr", self)
        theme_manager.register_item("abgr", self)
        theme_manager.register_item("hbgr", self)
        theme_manager.register_item("sel", self)
        self.image = image
        self.image1 = image1

class RadioButton(tk.Radiobutton):
    def __init__(self,parent,theme_manager,text,image,image1,func,var,value):
        tk.Radiobutton.__init__(self,parent, text=text, image=image, selectimage=image1, compound="center", variable=var, command=func, value=value, bd=0, font=("Rockwell", 14), pady=0, highlightthickness=0, indicatoron=0)
        theme_manager.register_item("bgr", self)
        theme_manager.register_item("abgr", self)
        theme_manager.register_item("hbgr", self)
        theme_manager.register_item("sel", self)
        theme_manager.register_item("txt", self)
        self.image = image
        self.image1 = image1

# - VIDEO ITEMS
class VideoQueue(tk.Frame):
    # Variables
    videos = []
    theme_manager = None

    boxes = []
    text = []

    render_height = 100
    render_spacing = 4

    # Constructor
    def __init__(self, parent, theme_manager, player):
        # Bind video player
        self.player = player
        # Get maximum buffer size
        self.config = configparser.ConfigParser()
        self.config.read("config.ini")
        self.buffer_size = int(self.config.get("Video", "Buffer_Size"))
        # Call superclass constructor
        tk.Frame.__init__(self, parent)
        # Configure column and row weights
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(0, weight=1)
        # Register and configure canvas for scrollable items
        self.scrollitems = tk.Canvas(self, scrollregion=(0, 0, 0, 0))
        self.scrollitems.grid(row=0, column=0, sticky="nesw")
        self.scrollitems.grid_columnconfigure(0, weight=1)
        theme_manager.register_item("bgr", self.scrollitems)
        theme_manager.register_item("hbgr", self.scrollitems)
        # Register scrollbar for scrolling through items
        self.scrollbar = tk.Scrollbar(self, orient="vertical")
        self.scrollbar.grid(row=0, column=1, sticky="nesw")
        # Bind scrollbar to frame
        self.scrollbar.config(command=self.scrollitems.yview)
        self.scrollitems.config(yscrollcommand=self.scrollbar.set)
        # Bind self theme manager
        self.theme_manager = theme_manager
        # Register update event
        self.theme_manager.register_callback(self.on_theme_change)
        # Register mouse click events
        self.scrollitems.bind("<Button-1>", self.mouse_down)

    def mouse_down(self, event):
        # Return if no videos are present
        if (len(self.videos) <= 0):
            return
        # Get position accounting for scroll offset
        canvas = event.widget
        x = canvas.canvasx(event.x)
        y = canvas.canvasy(event.y)
        # Attempt to find the clicked element and map to a video
        video_count = 0
        for box in self.boxes:
            x1, y1, x2, y2 = canvas.bbox(box)
            if (x1 <= x and x <= x2 and y1 <= y and y <= y2):
                # Get the player and set the video source
                video = self.videos[video_count].file
                self.player.set_source(video)
                break
            else:
                video_count += 1

    # Function to add multiple videos
    def add_videos(self, videos):
        # Iterate and call add video for all in the array
        for video in videos:
            self.add_video(video)

    # Function to add a video
    def add_video(self, video):
        # Check if the video is already contained
        for v in self.videos:
            if (v.file == video):
                return
        # Add video to the array
        video_input = iomanager.VideoInput(video, self.buffer_size)
        self.videos.append(video_input)
        # Check if the video is the first video - if so, set as the playing content
        if (len(self.videos) == 1):
            self.player.set_source(video)
        # Get videos count
        count = len(self.videos)
        # Create video render
        y1 = (count * self.render_height) - self.render_height
        if (count > 1):
            y1 += (count - 1) * 4
        # Render draw box
        box_id = self.scrollitems.create_rectangle(0, y1, self.scrollitems.winfo_width(), y1 + 100, fill=self.theme_manager.current_theme.container(), outline="")
        self.boxes.append(box_id)
        # Render video text
        video_text = self.scrollitems.create_text(10, y1 + 10, fill=self.theme_manager.current_theme.text(), text="Video: " + video, anchor="w")
        self.text.append(video_text)
        video_length = self.scrollitems.create_text(10, y1 + 24, fill=self.theme_manager.current_theme.text(), text="Length: " + video_input.video_length_str, anchor="w")
        self.text.append(video_length)
        # Configure scroll item height
        self.scrollitems.config(scrollregion=(0, 0, 0, (count * (self.render_height + self.render_spacing)) - self.render_spacing))

    # Function to clear the videos
    def clear_videos(self):
        # Clear arrays
        self.videos = []
        self.boxes = []
        self.text = []
        # Clear the video render drawings
        self.scrollitems.delete("all")

    # Function to get the videos
    def get_videos(self):
        return self.videos

    # Callback function for when the theme has been changed
    def on_theme_change(self, theme):
        # Update box colours
        for box in self.boxes:
            self.scrollitems.itemconfig(box, fill=theme.container())
        # Update text colours
        for txt in self.text:
            self.scrollitems.itemconfig(txt, fill=theme.text())

class VideoPlayer(tk.Frame):
    # Variables
    width = None
    height = None
    canvas = None
    source = None
    source_input = None
    frame = None
    playing = False
    scheduler = None
    controls_frame = None
    controls_play = None
    controls_trackbar = None
    play_image = None
    play_image_hover = None
    pause_image = None
    pause_image_hover = None
    buffer_size = 128
    buffer = None

    drawn = 0

    # Constructor
    def __init__(self, parent, theme_manager):
        # Get maximum buffer size
        self.config = configparser.ConfigParser()
        self.config.read("config.ini")
        self.buffer_size = int(self.config.get("Video", "Buffer_Size"))
        # Create read buffer
        self.buffer = Queue(maxsize=self.buffer_size + 1)
        # Load images
        self.play_image = ImageTk.PhotoImage(file="../Assets/ButtonPlay.png")
        self.play_image_hover = ImageTk.PhotoImage(file="../Assets/ButtonPlayHover.png")
        self.pause_image = ImageTk.PhotoImage(file="../Assets/ButtonPause.png")
        self.pause_image_hover = ImageTk.PhotoImage(file="../Assets/ButtonPauseHover.png")
        # Call superclass constructor
        tk.Frame.__init__(self, parent)
        theme_manager.register_item("bgr", self)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_columnconfigure(0, weight=1)
        # Create canvas
        self.canvas = tk.Canvas(self, bg="black")
        self.canvas.grid(row=0, column=0, sticky="nesw")
        theme_manager.register_item("hbgr", self.canvas)
        self.width = self.canvas.winfo_width()
        self.height = self.canvas.winfo_height()
        self.canvas.bind("<Configure>", self.on_resize)
        # Create player bar
        self.controls_frame = tk.Frame(self)
        self.controls_frame.grid(row=1, column=0, sticky="nesw", padx=10, pady=8)
        self.controls_frame.grid_columnconfigure(0, weight=1)
        self.controls_frame.grid_rowconfigure(0, weight=0)
        self.controls_frame.grid_rowconfigure(1, weight=0)
        theme_manager.register_item("bgr", self.controls_frame)
        self.controls_play = tk.Button(self.controls_frame, bd=0, image=self.play_image, command=self.toggle)
        self.controls_play.grid(row=0, column=0, sticky="ns")
        theme_manager.register_item("bgr", self.controls_play)
        theme_manager.register_item("abgr", self.controls_play)
        # Create player trackbar
        self.controls_trackbar = VideoTrackbar(self.controls_frame, theme_manager, self)
        self.controls_trackbar.grid(row=1, column=0, sticky="nesw")
        # Bind hover events
        self.controls_play.bind("<Enter>", self.play_hover)
        self.controls_play.bind("<Leave>", self.play_leave)

    # Function for when the mouse starts hovering the play button
    def play_hover(self, event):
        # Check if the video is playing
        if (self.playing):
            self.controls_play.configure(image=self.pause_image_hover)
        else:
            self.controls_play.configure(image=self.play_image_hover)

    # Function for when the mouse stops hovering the play button
    def play_leave(self, event):
        # Check if the video is playing
        if (self.playing):
            self.controls_play.configure(image=self.pause_image)
        else:
            self.controls_play.configure(image=self.play_image)

    # Function to set the video source
    def set_source(self, video):
        # Return if already the same source
        if (video == self.source):
            return
        # Stop playing if the player is
        if (self.playing):
            self.stop()
        # Update to new source
        self.source = video
        self.source_input = iomanager.VideoInput(self.source, self.buffer_size)
        # Clear any buffered frames
        with self.buffer.mutex:
            self.buffer.queue.clear()
        # Show the first frame of the new source
        self.first_rendered = False
        self._draw_single_frame()

    # Function to toggle the video playing state
    def toggle(self):
        # Check a source is present
        if (not self.source is None and not self.source_input is None):
            # Check if playing
            if (self.playing):
                # Stop playing
                self.pause()
                # Update button state
                self.controls_play.configure(image=self.pause_image_hover)
            else:
                # Start playing
                self.play()
                # Update button state
                self.controls_play.configure(image=self.play_image_hover)

    # Function to play the video
    def play(self):
        # Check a source is present
        if (not self.source is None and not self.source_input is None):
            # Mark as playing
            self.playing = True
            # Start reading frames
            self.source_input.start(self.buffer)
            # Run timer to play frames
            timer = Timer(interval=self.source_input.frames_interval, function=self._draw_frame, args=[self.buffer])
            timer.daemon = True
            timer.start()

    # Function to pause the video
    def pause(self):
        # Check a source is present
        if (not self.source is None and not self.source_input is None):
            # Update flags
            self.playing = False
            self.source_input.stop()

    # Function to stop the video
    def stop(self):
        # Check a source is present
        if (not self.source is None and not self.source_input is None):
            # Update flags
            self.playing = False
            self.source_input.close()
            self.source = None
            self.source_input = None
            # Reset drawn frame count
            self.drawn = 0

    # Function to jump to a specific frame
    def jump_frame(self, frame_number):
        # Check a source is present
        if (not self.source is None and not self.source_input is None):
            # Clear any buffered frames
            with self.buffer.mutex:
                self.buffer.queue.clear()
            # Set the current frame property
            self.drawn = frame_number
            self.source_input.frames_done = frame_number

    def _draw_single_frame(self):
         # Check a source is present
        if (not self.source is None and not self.source_input is None):
            # Render the first frame
            self.source_input.start(self.buffer)
            # Wait a small delay to read frame
            time.sleep(0.2)
            # Stop filling buffer
            self.source_input.stop()
            # Get the first frame
            try:
                # Get the frame
                frame = self.buffer.get(block=False)
                # Process the frame and resize correctly
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame = Image.fromarray(frame)
                frame.thumbnail((self.width, self.height), Image.ANTIALIAS)
                frame = ImageTk.PhotoImage(image=frame)
                # Draw the image
                self.canvas.create_image(self.width/2, self.height/2, image=frame, anchor=tk.CENTER)
                self.frame = frame
                # Increment drawn count
                self.drawn += 1
                # Update trackbar progress
                self.controls_trackbar.update(self.drawn, self.source_input.frames_total)
            except:
                # Return - no frame found
                return

    # Function to draw a frame
    def _draw_frame(self, target):
        # Return if not playing
        if (not self.playing):
            return
        # Get the next frame
        try:
            # Call next frame draw
            timer = Timer(interval=self.source_input.frames_interval, function=self._draw_frame, args=[self.buffer])
            timer.daemon = True
            timer.start()
            # Get the frame
            frame = target.get(block=False)
            # Process the frame and resize correctly
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = Image.fromarray(frame)
            frame.thumbnail((self.width, self.height), Image.ANTIALIAS)
            frame = ImageTk.PhotoImage(image=frame)
            # Draw the image
            self.canvas.create_image(self.width/2, self.height/2, image=frame, anchor=tk.CENTER)
            self.frame = frame
            # Increment drawn count
            self.drawn += 1
            # Update trackbar progress
            self.controls_trackbar.update(self.drawn, self.source_input.frames_total)
        except:
            # Return - no frame found
            return

    # Function to handle frame resizing
    def on_resize(self, event):
        self.width = event.width
        self.height = event.height

class VideoTrackbar(tk.Canvas):
    # Variables
    player = None
    current_frame = 0
    end_frame = 0
    percent = 0
    mousedown = False

    last_elapsed = -1
    last_end = -1
    last_time = "0:00:00 / 0:00:00"

    dragged_frame = None
    dragged_playing = False
    dragged_last_time = time.time()

    # Constructor
    def __init__(self, parent, theme_manager, player):
        # Bind parent
        self.player = player
        # Call superclass constructor
        tk.Canvas.__init__(self, parent, highlightthickness=0, height=50)
        theme_manager.register_item("bgr", self)
        # Bind theme manager to object variable
        self.theme_manager = theme_manager
        # Initialize variables
        self.current_frame = 0
        self.end_frame = 0
        # Register resize listener
        self.bind('<Configure>', self._resize)
        # Register theme change callback
        self.theme_manager.register_callback(self.on_theme_change)

    # Function to reset the trackbar to default
    def reset(self):
        # Update variables
        self.current_frame = 0
        self.end_frame = 0
        self.percent = 0
        # Call redraw functions with new frames
        self.redraw()
        self._draw_time()

    # Update the current progress bar
    def update(self, current_frame, end_frame):
        # Update variables
        self.current_frame = current_frame
        self.end_frame = end_frame
        # Calculate percentage completion from frames
        if (self.current_frame >= 0 and self.end_frame > 0):
            self.percent = (self.current_frame / self.end_frame)
        # Call redraw functions with new frames
        self.redraw()
        self._draw_time()

    # Redraw the progress bar without new frames
    def redraw(self):
        # Check if the current frame and end frame are both zero - if so, no video is playing
        if (self.current_frame == 0 and self.end_frame == 0):
            self._draw_pointer(0)
        else:
            # Calculate current point from percentage
            point = (self.w - 20) * self.percent
            self._draw_pointer(point)

    # Function for when the mouse is pressed down
    def mouse_down(self, event):
        # Get the bar coordinates
        bar = self.coords(self.bar_end)
        # Check if the click was on the bar
        if (event.x >= bar[0] and event.x <= bar[2] and event.y >= bar[1] and event.y <= bar[3]):
            # Check if the video player has a source
            if (self.player.source is None):
                return
            self.mousedown = True
            # Check if the video player is playing
            if (self.player.playing):
                self.dragged_playing = True
                self.player.pause()
            # Draw new pointer
            self._draw_pointer(event.x - 10)
            # Calculate new frame location
            width = bar[2] - bar[0]
            pos = event.x - bar[0]
            # Calculate a multiplication factor to go to the new frame
            factor = pos / width
            # Calculate new frame position
            self.dragged_frame = math.floor(self.end_frame * factor)

    # Function for when the mouse is released
    def mouse_up(self, event):
        # Set to false
        if (not self.mousedown):
            return
        self.mousedown = False
        # Jump to the new calculated frame
        if (not self.dragged_frame is None):
            self.player.jump_frame(self.dragged_frame)
            self.dragged_frame = None
        # Await small delay for frames to settle
        time.sleep(0.1)
        # Restart player if playing when dragged
        if (self.dragged_playing):
            self.player.play()
            self.dragged_playing = False
        else:
            self.player._draw_single_frame()

    # Function for when the mouse is dragged
    def mouse_drag(self, event):
        # Return if mouse is not pressed down
        if (not self.mousedown):
            return
        # Get the bar coordinates
        bar = self.coords(self.bar_end)
        # Check if the click was within valid x bounds
        if (event.x >= bar[0] and event.x <= bar[2]):
            self._draw_pointer(event.x - 10)
            # Calculate new frame location
            width = bar[2] - bar[0]
            pos = event.x - bar[0]
            # Calculate a multiplication factor to go to the new frame
            factor = pos / width
            # Calculate new frame position
            self.dragged_frame = math.floor(self.end_frame * factor)
            # Draw the dragged frame time
            self._draw_dragged_time(self.dragged_frame)

    # Function for when the canvas is resized
    def _resize(self, event):
        # Get the new width
        self.w = event.width - 10
        # Delete previous elements
        self.delete("all")
        # Draw full empty bar
        self.bar_end = self.create_rectangle(15, 32, self.w - 10, 38)
        self.bar_start = self.create_rectangle(15, 32, self.w - 10, 38)
        # Draw trackbar pointer
        self.tracker_outer = self.create_oval(21, 18, 35, 32)
        self.tracker_inner = self.create_oval(23, 20, 33, 30)
        # Draw time text
        self.time_text = self.create_text(10, 10, text="0:00:00 / 0:00:00", anchor="w")
        # Add callback events for trackbar srolling
        self.bind("<Button-1>", self.mouse_down)
        self.bind("<ButtonRelease-1>", self.mouse_up)
        self.bind("<Motion>", self.mouse_drag)
        # Redraw the progress
        self.redraw()

    # Function to draw the pointer at the specified location
    def _draw_pointer(self, x):
        # Draw filled portion of bar
        self.coords(self.bar_start, 15, 32, x + 10, 38)
        # Draw trackbar pointer
        self.coords(self.tracker_outer, x + 3, 28, x + 17, 42)
        self.coords(self.tracker_inner, x + 5, 30, x + 15, 40)

    # Function to draw the dragged time progress on the video
    def _draw_dragged_time(self, frame):
        # Get video FPS
        fps = self.player.source_input.frames_fps
        elapsed = math.floor(frame / fps)
        total = math.floor(self.end_frame / fps)
        # Check if elapsed and total match the last time
        if (elapsed == self.last_elapsed and total == self.last_end):
            return
        # Update to new time
        self.last_elapsed = elapsed
        self.last_end = total
        # Convert seconds to displayable time
        self.last_time = str(datetime.timedelta(seconds=elapsed)) + " / " + str(datetime.timedelta(seconds=total))
        # Draw the time string
        self.itemconfig(self.time_text, text=self.last_time)

    # Function to draw the time progress on the video
    def _draw_time(self):
        # Draw black if video has no source and return
        if (self.player.source_input is None):
            # Draw no time default
            if (not self.last_time == "0:00:00 / 0:00:00"):
                self.itemconfig(self.time_text(text="0:00:00 / 0:00:00"))
                self.last_time = "0:00:00 / 0:00:00"
        else:
            # Get video FPS
            fps = self.player.source_input.frames_fps
            elapsed = math.floor(self.current_frame / fps)
            total = math.floor(self.end_frame / fps)
            # Check if elapsed and total match the last time
            if (elapsed == self.last_elapsed and total == self.last_end):
                return
            # Update to new time
            self.last_elapsed = elapsed
            self.last_end = total
            # Convert seconds to displayable time
            self.last_time = str(datetime.timedelta(seconds=elapsed)) + " / " + str(datetime.timedelta(seconds=total))
            # Draw the time string
            self.itemconfig(self.time_text, text=self.last_time)

    # Callback function for when the theme has been changed
    def on_theme_change(self, theme):
        # Update bar colours
        self.itemconfig(self.bar_end, fill=theme.hover())
        self.itemconfig(self.bar_start, fill=theme.text())
        # Update pointer colours
        self.itemconfig(self.tracker_outer, fill=theme.background())
        self.itemconfig(self.tracker_inner, fill=theme.container())
        # Update time text colour
        self.itemconfig(self.time_text, fill=theme.text())

# - APP ITEMS
class AppToolbar(tk.Frame):
    # Variables
    icon = None
    button_frame = None
    buttons = []
    parent = None

    # Images
    image_title = None

    # Constructor
    def __init__(self, parent):
        # Call superclass constructor
        tk.Frame.__init__(self, parent)
        # Bind parent for theme manager later
        self.parent = parent
        self.grid(row=0, column=0, sticky="nesw", pady=(0, 4))
        parent.theme_manager.register_item("ctr", self)
        # Load images
        self.image_title = ImageTk.PhotoImage(file="../Assets/TitleBarDark.png")
        # Set grid values
        self.grid_rowconfigure(0, weight=0)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        # Add title and spacing container
        self.icon = tk.Label(self, image=self.image_title, bd=0, highlightthickness=0)
        self.icon.grid(row=0, column=0, sticky="nsw")
        parent.theme_manager.register_item("ctr", self.icon)
        # Frame for the buttons
        self.button_frame = tk.Frame(self)
        self.button_frame.grid(row=0, column=1, padx=4, pady=(11, 0), sticky="es")
        parent.theme_manager.register_item("ctr", self.button_frame)

    # Function for when a button is clicked
    def button_click(self, item, callback):
        # Change active button
        for btn in self.buttons:
            if (btn == item):
                btn.set_active(True)
            else:
                btn.set_active(False)
        # Call button callback function
        callback()

    # Function to add a button to the toolbar
    def add_button(self, text, callback):
        btn = MenuButton(self.button_frame, text, lambda: self.button_click(btn, callback), self.parent.theme_manager)
        btn.grid(row=0, column=len(self.buttons), padx=4)
        self.parent.theme_manager.register_item("ctr", btn)
        self.buttons.append(btn)
        return btn

    # Function to remove a button from the toolbar
    def remove_button(self, btn):
        self.buttons.remove(btn)
        btn.destroy()
        for i in range(0, len(self.buttons)):
            self.buttons[i].grid(row=0, column=i)

class AppPageView(tk.Frame):
    # Variables
    frames = []

    # Constructor
    def __init__(self, parent, theme_manager):
        tk.Frame.__init__(self, parent)
        theme_manager.register_item("ctr", self)
        # Set grid values
        self.grid(column=0, row=1, sticky="nesw")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        # Assign parent
        self.app = parent

    # Function to add a page to the view
    def add_page(self, pagetype):
        page = pagetype(self)
        self.frames.append(page)
        return page

class AppStatusBar(tk.Frame):
    # Variables
    status_label = None
    status = "Ready to process."

    # Constructor
    def __init__(self, parent, copyright, theme_manager):
        # Frame for the status bar
        tk.Frame.__init__(self, parent)
        theme_manager.register_item("ctr", self)
        self.grid(row=2, column=0, sticky="nesw", pady=(4, 0))
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        # Status bar text
        self.status_label = tk.Label(self, text="Status: Ready to process.")
        theme_manager.register_item("ctr", self.status_label)
        theme_manager.register_item("txt", self.status_label)
        self.status_label.grid(row=0, column=0, sticky="nsw", pady=2, padx=10)
        # Copyright text
        label = tk.Label(self, text=copyright)
        theme_manager.register_item("ctr", label)
        theme_manager.register_item("txt", label)
        label.grid(row=0, column=1, sticky="nes", pady=2, padx=10)

    # Function to update the status
    def set_status(self, status):
        self.status_label.configure(text="Status: " + str(status))
        self.status = status

    # Function to get the status
    def get_status(self):
        return self.status

# - THEME ITEMS
class Theme:
    def __init__(self, name, bgcolor, hvrcolor, cntrcolor, txtcolor):
        self._name = name
        self._bgcolor = bgcolor
        self._hvrcolor = hvrcolor
        self._cntrcolor = cntrcolor
        self._txtcolor = txtcolor

    def title(self):
        return self._name

    def background(self):
        return self._bgcolor

    def hover(self):
        return self._hvrcolor

    def container(self):
        return self._cntrcolor

    def text(self):
        return self._txtcolor

    def change_theme(self, name, bgcolor, hvrcolor, cntrcolor, txtcolor):
        self.__init__(name, bgcolor, hvrcolor, cntrcolor, txtcolor)

class ThemeManager:
    # Variables
    themes = []
    current_theme = None
    items = {
        "bgr": [],
        "hvr": [],
        "ctr": [],
        "txt": [],
        "abgr": [],
        "actr": [],
        "hbgr": [],
        "sel": [],
        "face": []
    }
    container = None
    callbacks = []

    # Constructor
    def __init__(self, container):
        # Load themes
        self.register_theme(Theme("Dark", "#202020", "#2B2B2B", "#383838", "#D4D4D4"))
        self.register_theme(Theme("Light", "#EDEDED", "#76CBE3", "#F5F5F5", "#009696"))
        self.register_theme(Theme("Debug", "#000FFF", "#00FF00", "#FFF100", "#FF0000"))

    # Register a theme
    def register_theme(self, theme):
        # Append the added theme
        self.themes.append(theme)

    # Function to register the item
    def register_item(self, objtype, obj):
        # Append the new item on the correct type
        self.items[objtype].append(obj)

    # Register a callback function
    def register_callback(self, func):
        # Append the callback function
        self.callbacks.append(func)

    # Apply a theme
    def apply_theme(self, theme):
        # Update the current theme
        self.current_theme = theme
        # Iterate background items
        for item in self.items["bgr"]:
            item.configure(bg=theme._bgcolor)
        # Iterate container items
        for item in self.items["ctr"]:
            item.configure(bg=theme._cntrcolor)
        # Iterate text items
        for item in self.items["txt"]:
            item.configure(fg=theme._txtcolor)
        # Iterate active background items
        for item in self.items["abgr"]:
            item.configure(activebackground=theme._bgcolor)
        # Iterate active container items
        for item in self.items["actr"]:
            item.configure(activebackground=theme._cntrcolor)
        # Iterate highlight container items
        for item in self.items["hbgr"]:
            item.configure(highlightbackground=theme._cntrcolor)
        # Iterate select container items
        for item in self.items["sel"]:
            item.configure(selectcolor=theme._bgcolor)
        # Iterate face colour container items
        for item in self.items["face"]:
            item.configure(facecolor=theme._bgcolor)
        # Iterate callback functions and invoke
        for func in self.callbacks:
            func(theme)

    # Function to apply a theme based on name
    def apply_theme_name(self, theme_name):
        # Get the theme from name
        new_theme = next((t for t in self.themes if t._name == theme_name), None)
        # Apply the theme
        self.apply_theme(new_theme)

    # Function to apply the last theme
    def apply_last_theme(self):
        # Get the last theme
        theme = self.get_last_theme()
        # Apply the last theme
        self.apply_theme_name(theme)

    # Function to get the current theme
    def get_current_theme(self):
        return self.current_theme

    # Get the last used theme
    def get_last_theme(self):
        # Create config and read file
        self.config = configparser.ConfigParser()
        self.config.read("config.ini")
        v = self.config.get('General', 'Theme')
        # Set the theme by name
        return v
