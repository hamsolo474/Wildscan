import os
import threading
import webbrowser
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox
from typing import Callable, Iterable, Optional

try:
    from PIL import Image, ImageTk
except ModuleNotFoundError:
    import subprocess
    subprocess.check_call(sys.executable, '-m', 'pip', 'install', 'pillow')
    from PIL import Image, ImageTk

class SimpleRunnerGUI(tk.Frame):
    """
    Arguments:
      master: parent widget
      models: iterable of model names for the dropdown (default: ["default"])
      run_callback: Callable invoked when Run is pressed:
          signature: fn(model: str, input_path: str, output_path: str, on_done: Callable[[bool, str], None])
          - on_done(success: bool, message: str) should be called by run task when finished.
          If run_callback runs long work, it should return immediately and perform work asynchronously.
    """

    def __init__(
        self,
        master,
        models: Optional[Iterable[str]] = None,
        output_mode: Optional[Iterable[str]] = None,
        run_callback: Optional[Callable] = None,
        default_input:  str = os.sep.join([os.getcwd(),"INPUT_IMAGES"]),
        default_output: str = os.sep.join([os.getcwd(),"OUTPUT_IMAGES"]),
        **kwargs
    ):
        super().__init__(master, **kwargs)
        self.master = master
        self.models = list(models) if models else ["default"]
        self.output_mode = "Original images"
        self.output_modes = ["Original images", "Annotated images"]
        self.run_callback = run_callback or self._default_run_callback
        self.day_conf_default = 15
        self.night_conf_default = 30

        self._build_ui(default_input, default_output)

    def _build_ui(self, default_input: str, default_output: str):
        pad = {"padx": 8, "pady": 6}

        row = 0
        try:
            img = Image.open('logo.jpg').convert("RGBA")
            img = img.resize((64,64), Image.LANCZOS)
            self.tk_image = ImageTk.PhotoImage(img)

            # Image label
            lbl_img = ttk.Label(self, image=self.tk_image)
            lbl_img.grid(row=row, column=0, sticky="w", **pad)

        except FileNotFoundError as e:
            print(f'ERROR: {e}')

        font = tkfont.Font(size=25)
        lbl_model = ttk.Label(self, text="Wildscan", font=font)
        lbl_model.grid(row=row, column=1, sticky="w", **pad)

        row += 1
        # Model selector
        lbl_model = ttk.Label(self, text="Model:")
        lbl_model.grid(row=row, column=0, sticky="w", **pad)

        self.model_var = tk.StringVar(value=self.models[0])
        cmb = ttk.Combobox(self, textvariable=self.model_var, values=self.models, state="readonly")
        cmb.grid(row=row, column=1, columnspan=2, sticky="ew", **pad)

        row += 1
        # Threshold Sliders
        lbl_day_conf_scale = ttk.Label(self, text=f'Day Conf: (Default {self.day_conf_default}%)')
        lbl_day_conf_scale.grid(row=row, column=0, sticky="w", **pad)
        self.day_conf_scale_var = tk.IntVar(value=self.day_conf_default)
        day_conf_scale = ttk.Scale(self, from_=1, to=100, orient="horizontal", command=self.day_conf_scale_move)
        day_conf_scale.set(self.day_conf_default)
        day_conf_scale.grid(row=row, column=1, columnspan=1, sticky="ew", **pad)
        self.day_conf_scale_val_label = ttk.Label(self, text=str(self.day_conf_default), width=4)
        self.day_conf_scale_val_label.grid(row=row, column=2, sticky="w", **pad)

        row += 1
        lbl_night_conf_scale = ttk.Label(self, text=f'Night Conf: (Default {self.night_conf_default}%)')
        lbl_night_conf_scale.grid(row=row, column=0, sticky="w", **pad)
        self.night_conf_scale_var = tk.IntVar(value=self.night_conf_default)
        night_conf_scale = ttk.Scale(self, from_=1, to=100, orient="horizontal", command=self.night_conf_scale_move)
        night_conf_scale.set(self.night_conf_default)
        night_conf_scale.grid(row=row, column=1, columnspan=1, sticky="ew", **pad)
        self.night_conf_scale_val_label = ttk.Label(self, text=str(self.night_conf_default), width=4)
        self.night_conf_scale_val_label.grid(row=row, column=2, sticky="w", **pad)

        row += 1
        #Output mode selector
        lbl_output_mode = ttk.Label(self, text="Output mode:")
        lbl_output_mode.grid(row=row, column=0, sticky="w", **pad)

        self.output_mode_var = tk.StringVar(value=self.output_modes[0])
        cmb = ttk.Combobox(self, textvariable=self.output_mode_var, values=self.output_modes, state="readonly")
        cmb.grid(row=row, column=1, columnspan=2, sticky="ew", **pad)

        row += 1
        # Input folder
        lbl_in = ttk.Label(self, text="Input folder:")
        lbl_in.grid(row=row, column=0, sticky="w", **pad)

        self.input_var = tk.StringVar(value=default_input)
        ent_in = ttk.Entry(self, textvariable=self.input_var)
        ent_in.grid(row=row, column=1, columnspan=2, sticky="ew", **pad)

        btn_in = ttk.Button(self, text="Browse...", command=self._choose_input_folder)
        btn_in.grid(row=row, column=2, sticky="e", **pad)

        row += 1
        # Output folder
        lbl_out = ttk.Label(self, text="Output folder:")
        lbl_out.grid(row=row, column=0, sticky="w", **pad)

        self.output_var = tk.StringVar(value=default_output)
        ent_out = ttk.Entry(self, textvariable=self.output_var)
        ent_out.grid(row=row, column=1, columnspan=2, sticky="ew", **pad)

        btn_out = ttk.Button(self, text="Browse...", command=self._choose_output_folder)
        btn_out.grid(row=row, column=2, sticky="e", **pad)

        row += 1
        # Run button
        self.run_btn = ttk.Button(self, text="Run", command=self._on_run)
        self.run_btn.grid(row=row, column=0, columnspan=3, sticky="ew", **pad)

        # Grid weight
        self.columnconfigure(1, weight=1)

    def day_conf_scale_move(self, raw_value):
        val = int(float(raw_value))
        self.day_conf_scale_var.set(val)
        self.day_conf_scale_val_label.config(text=str(val))

    def night_conf_scale_move(self, raw_value):
        val = int(float(raw_value))
        self.night_conf_scale_var.set(val)
        self.night_conf_scale_val_label.config(text=str(val))

    def _choose_input_folder(self):
        path = filedialog.askdirectory(title="Select input folder", initialdir=self.input_var.get())
        if path:
            self.input_var.set(path)

    def _choose_output_folder(self):
        path = filedialog.askdirectory(title="Select output folder", initialdir=self.output_var.get())
        if path:
            self.output_var.set(path)

    def _on_run(self):
        pad = {"padx": 8, "pady": 6}
        row = 8
        # Status label (small)
        self.status_var = tk.StringVar(value="")
        lbl_status = ttk.Label(self, textvariable=self.status_var, foreground="gray")
        lbl_status.grid(row=row, column=0, columnspan=1, sticky="w", padx=8, pady=(0,8))

        row += 1
        # Progress bar
        self.progress_var = tk.IntVar(value=0)
        self.progress_total = 0
        self.progressbar = ttk.Progressbar(self, variable=self.progress_var, maximum=100, mode='determinate')
        self.progressbar.grid(row=row, column=0, columnspan=2, sticky='ew', **pad)
        self.progress_label_var = tk.StringVar(value="Processed 0/0")
        lbl_progress = ttk.Label(self, textvariable=self.progress_label_var)
        lbl_progress.grid(row=row, column=2, sticky="e", **pad)

        #model = self.model_var.get()
        input_path = self.input_var.get().strip()
        #day_conf=self.day_conf_scale_var.get()
        #night_conf=self.night_conf_scale_var.get()
        output_path = self.output_var.get().strip()
        #output_mode = self.output_mode_var.get().strip()

        if not input_path or not os.path.isdir(input_path):
            messagebox.showerror("Input folder required", "Please select a valid input folder.")
            return
        if not output_path:
            messagebox.showerror("Output folder required", "Please select an output folder.")
            return
        if not os.path.isdir(output_path):
            try:
                os.makedirs(output_path, exist_ok=True)
            except Exception as e:
                messagebox.showerror("Cannot create output folder", str(e))
                return

        # disable run button while running
        self.run_btn.config(state="disabled")
        self.status_var.set("Running...")

        # Expect run_callback to call on_done when finished. Run in a thread to avoid blocking UI.
        def run_wrapper():
            try:
                def progress_callback(processed: int, total: int):
                    self.master.after(0, lambda: self._update_progress(processed, total))
                # Provide an on_done callback that marshals back to main thread
                def on_done(success: bool, message: str):
                    self.master.after(0, lambda: self._run_finished(success, message, output_path))

                # If run_callback is synchronous and long, run it in this worker thread.
                self.run_callback(model       = self.model_var.get(),
                                  input_path  = self.input_var.get().strip(),
                                  output_path = self.output_var.get().strip(),
                                  output_mode = self.output_mode_var.get().strip(),
                                  day_conf    = self.day_conf_scale_var.get(),
                                  night_conf  = self.night_conf_scale_var.get(),
                                  on_done=on_done,
                                  progress_callback=progress_callback,
                                  verbose=True)
            #except Exception as e:
            except KeyError:
                self.master.after(0, lambda: self._run_finished(False, "Error: ", output_path))

        threading.Thread(target=run_wrapper, daemon=True).start()

    def _update_progress(self, processed: int, total: int):
        self.progress_total = total
        self.progress_label_var.set(f'Processed {processed}/{self.progress_total}')
        if self.progress_total > 0:
            percent = int(processed*100/self.progress_total)
            self.progressbar.config(mode='determinate', maximum=100)
            self.progress_var.set(percent)
        #self.status_var.set(f"Processing")

    def _run_finished(self, success: bool, message: str, output_path: str):
        self.run_btn.config(state="normal")
        self.status_var.set("" if success else f"Failed: {message}")

        # Show popup with message and button to open folder
        self._show_result_popup(success, message, output_path)

    def _show_result_popup(self, success: bool, message: str, output_path: str):
        title = "Success" if success else "Finished"
        # Use a simple top-level window rather than messagebox so we can add a button
        top = tk.Toplevel(self)
        top.title(title)
        top.transient(self.master)
        top.grab_set()

        frm = ttk.Frame(top, padding=12)
        frm.pack(fill="both", expand=True)

        lbl = ttk.Label(frm, text=message, wraplength=600)
        lbl.pack(padx=4, pady=(0,12))

        btn_open = ttk.Button(frm, text="Open output folder", command=lambda: self._open_folder(output_path))
        btn_open.pack(side="left", padx=(0,6))

        btn_close = ttk.Button(frm, text="Close", command=top.destroy)
        btn_close.pack(side="right", padx=(6,0))

        # Center the popup over parent
        top.update_idletasks()
        x = self.master.winfo_rootx() + (self.master.winfo_width() - top.winfo_width()) // 2
        y = self.master.winfo_rooty() + (self.master.winfo_height() - top.winfo_height()) // 2
        top.geometry(f"+{x}+{y}")

    def _open_folder(self, path: str):
        try:
            if os.name == "nt":
                os.startfile(os.path.abspath(path))
            elif os.name == "posix":
                # Try common desktop openers
                if shutil_which("xdg-open"):
                    os.system(f'xdg-open "{path}"')
                elif shutil_which("open"):
                    os.system(f'open "{path}"')
                else:
                    webbrowser.open("file://" + os.path.abspath(path))
            else:
                webbrowser.open("file://" + os.path.abspath(path))
        except Exception:
            # Fallback to opening via webbrowser
            webbrowser.open("file://" + os.path.abspath(path))

# small helper used in _open_folder
def shutil_which(name: str) -> Optional[str]:
    from shutil import which
    return which(name)


# Example standalone usage
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Wildscan")

    def real_run(model, input_path, output_path, output_mode, day_conf, night_conf, on_done, progress_callback, verbose=False):
        def worker():
            import detection_code as dc
            try:
                app = dc.app(model=model,
                             input_path=input_path,
                             output_path=output_path,
                             output_mode=output_mode,
                             day_conf=day_conf,
                             night_conf=night_conf,
                             progress_callback=progress_callback,
                             verbose=verbose)
                message = app.main()
                on_done(True, message)
            #except Exception as e:
            except KeyError as e:
                on_done(False, str(e))
        threading.Thread(target=worker, daemon=True).start()

    gui = SimpleRunnerGUI(root,
                          models=["Best", "Last"],
                          run_callback=real_run)
    gui.grid(padx=8, pady=6)
    #gui.pack(fill="both", expand=True, padx=12, pady=12)

    root.mainloop()
