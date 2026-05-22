import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from tkinterdnd2 import DND_FILES, TkinterDnD
from tkcalendar import DateEntry

from handlers.docx_handler import DOCXHandler
from handlers.pdf_handler import PDFHandler
from handlers.jpg_handler import JPGHandler
from handlers.png_handler import PNGHandler
from handlers.exe_handler import EXEHandler


class MetadataGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Metadata Analyzer")
        self.root.geometry("950x600")

        self.handler = None
        self.file_path = None

        self.handlers = {
            ".docx": DOCXHandler,
            ".pdf": PDFHandler,
            ".jpg": JPGHandler,
            ".jpeg": JPGHandler,
            ".png": PNGHandler,
            ".exe": EXEHandler,
        }

        self.selected_file = tk.StringVar()
        self.selected_type = tk.StringVar(value="No file loaded")

        self._build_layout()

    def _build_layout(self):
        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(fill="x")

        ttk.Label(top_frame, text="Selected file:").pack(side="left")

        file_entry = ttk.Entry(
            top_frame,
            textvariable=self.selected_file,
            state="readonly",
            width=90
        )
        file_entry.pack(side="left", padx=8, fill="x", expand=True)

        ttk.Button(
            top_frame,
            text="Open File",
            command=self.open_file_dialog
        ).pack(side="left")

        info_frame = ttk.Frame(self.root, padding=(10, 0))
        info_frame.pack(fill="x")

        ttk.Label(info_frame, textvariable=self.selected_type).pack(anchor="w")

        drop_frame = ttk.LabelFrame(
            self.root,
            text="Drag and drop file here",
            padding=20
        )
        drop_frame.pack(fill="x", padx=10, pady=10)

        drop_label = ttk.Label(
            drop_frame,
            text="Drop DOCX, PDF, JPG, PNG or EXE file",
            anchor="center"
        )
        drop_label.pack(fill="x")

        drop_frame.drop_target_register(DND_FILES)
        drop_frame.dnd_bind("<<Drop>>", self.handle_drop)

        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill="both", expand=True)

        self.metadata_tree = ttk.Treeview(
            main_frame,
            columns=("field", "value", "type"),
            show="headings"
        )

        self.metadata_tree.bind("<Double-1>", self.on_row_double_click)

        self.metadata_tree.heading("field", text="Field")
        self.metadata_tree.heading("value", text="Value")
        self.metadata_tree.heading("type", text="Type")

        self.metadata_tree.column("field", width=220)
        self.metadata_tree.column("value", width=520)
        self.metadata_tree.column("type", width=130)

        self.metadata_tree.pack(fill="both", expand=True, side="left")

        scrollbar = ttk.Scrollbar(
            main_frame,
            orient="vertical",
            command=self.metadata_tree.yview
        )
        scrollbar.pack(side="right", fill="y")
        self.metadata_tree.configure(yscrollcommand=scrollbar.set)

        bottom_frame = ttk.Frame(self.root, padding=10)
        bottom_frame.pack(fill="x")

        ttk.Label(bottom_frame, text="Editable field:").grid(row=0, column=0, sticky="w")

        self.field_var = tk.StringVar()
        self.field_combo = ttk.Combobox(
            bottom_frame,
            textvariable=self.field_var,
            width=30
        )
        self.field_combo.grid(row=0, column=1, padx=5)
        self.field_combo.bind("<<ComboboxSelected>>", self.on_field_selected)

        ttk.Label(bottom_frame, text="New value:").grid(row=0, column=2, sticky="w")

        self.value_entry = ttk.Entry(bottom_frame, width=45)
        self.value_entry.grid(row=0, column=3, padx=5)

        ttk.Button(
            bottom_frame,
            text="Update",
            command=self.update_metadata
        ).grid(row=0, column=4, padx=5)

        ttk.Button(
            bottom_frame,
            text="Clear Field",
            command=self.clear_metadata
        ).grid(row=0, column=5, padx=5)

        ttk.Button(
            bottom_frame,
            text="Refresh",
            command=self.refresh_view
        ).grid(row=0, column=6, padx=5)

    def open_file_dialog(self):
        file_path = filedialog.askopenfilename(
            title="Select file",
            filetypes=[
                ("Supported files", "*.docx *.pdf *.jpg *.jpeg *.png *.exe"),
                ("All files", "*.*"),
            ]
        )

        if file_path:
            self.load_file(file_path)

    def handle_drop(self, event):
        file_path = event.data.strip()

        if file_path.startswith("{") and file_path.endswith("}"):
            file_path = file_path[1:-1]

        self.load_file(file_path)

    def load_file(self, file_path):
        extension = os.path.splitext(file_path)[1].lower()

        if extension not in self.handlers:
            messagebox.showerror(
                "Unsupported format",
                f"Unsupported file format: {extension}"
            )
            return

        handler_class = self.handlers[extension]
        handler = handler_class(file_path)

        if not handler.read_metadata():
            messagebox.showerror("Error", "Could not read metadata from this file.")
            return

        self.file_path = file_path
        self.handler = handler

        self.selected_file.set(file_path)
        self.selected_type.set(f"Detected format: {extension.upper()}")

        self.refresh_view()

    def refresh_view(self):
        for row in self.metadata_tree.get_children():
            self.metadata_tree.delete(row)

        if not self.handler:
            return

        if not self.handler.read_metadata():
            messagebox.showerror("Error", "Could not refresh metadata.")
            return

        if hasattr(self.handler, "get_metadata"):
            data = self.handler.get_metadata()

            for key, value in data.get("statistics", {}).items():
                self.metadata_tree.insert("", "end", values=(key, value, "File"))

            for key, value in data.get("technical_metadata", {}).items():
                self.metadata_tree.insert("", "end", values=(key, value, "Technical"))

            for key, value in data.get("editable_metadata", {}).items():
                self.metadata_tree.insert("", "end", values=(key, value, "Editable"))

            for key, value in data.get("extended_metadata", {}).items():
                self.metadata_tree.insert("", "end", values=(key, value, "Extended"))

            for key, value in data.get("custom_metadata", {}).items():
                self.metadata_tree.insert("", "end", values=(key, value, "Custom"))

            editable_tags = (
                self.handler.get_editable_tags()
                if hasattr(self.handler, "get_editable_tags")
                else []
            )

        else:
            for key, value in self.handler.metadata.items():
                self.metadata_tree.insert("", "end", values=(key, value, "Metadata"))

            editable_tags = self.handler.get_tags()

        self.field_combo["values"] = editable_tags
        self.field_var.set("")

    def update_metadata(self):
        if not self.handler:
            messagebox.showwarning("Warning", "Load a file first.")
            return

        field = self.field_var.get()
        value = self.value_entry.get()

        if not field:
            messagebox.showwarning("Warning", "Select metadata field.")
            return

        if self.is_date_field(field) and not value:
            self.open_datetime_editor(field, "")
            return

        if self.is_gps_decimal_field(field) and not value:
            self.open_gps_decimal_editor(field, "")
            return

        if not hasattr(self.handler, "edit_metadata"):
            messagebox.showerror("Error", "This handler does not support editing.")
            return

        success = self.handler.edit_metadata(field, value)

        if success is not False:
            self.refresh_view()
            self.value_entry.delete(0, tk.END)
            messagebox.showinfo("Success", f"Updated field: {field}")

    def clear_metadata(self):
        if not self.handler:
            messagebox.showwarning("Warning", "Load a file first.")
            return

        field = self.field_var.get()

        if not field:
            messagebox.showwarning("Warning", "Select metadata field.")
            return

        if not hasattr(self.handler, "remove_tag"):
            messagebox.showerror("Error", "This handler does not support removing metadata.")
            return

        success = self.handler.remove_tag(field)

        if success is not False:
            self.refresh_view()
            messagebox.showinfo("Success", f"Cleared field: {field}")

    def on_row_double_click(self, event):
        selected_item = self.metadata_tree.selection()

        if not selected_item:
            return

        values = self.metadata_tree.item(selected_item[0], "values")

        if len(values) < 3:
            return

        field_name = values[0]
        current_value = values[1]
        field_type = values[2]

        editable_field = self._get_editable_field_name(field_name, field_type)

        if editable_field is None:
            messagebox.showinfo(
                "Read-only field",
                f"Field '{field_name}' is not editable."
            )
            return

        self.field_var.set(editable_field)

        if self.is_date_field(editable_field):
            self.open_datetime_editor(editable_field, current_value)
        elif self.is_gps_decimal_field(editable_field):
            self.open_gps_decimal_editor(editable_field, current_value)
        else:
            self.value_entry.delete(0, tk.END)
            self.value_entry.insert(0, current_value)
            self.value_entry.focus_set()

    def _get_editable_field_name(self, field_name, field_type):
        if not self.handler:
            return None

        editable_tags = self.handler.get_editable_tags()

        if field_name in editable_tags:
            return field_name

        gps_target = self.get_gps_target_field(field_name)
        if gps_target and gps_target in editable_tags:
            return gps_target

        extended_name = f"Extended:{field_name}"
        if extended_name in editable_tags:
            return extended_name

        return None

    def is_date_field(self, field):
        date_fields = [
            "Created",
            "Last Modified",
            "CreationDate",
            "DateTime",
            "DateTimeOriginal",
            "DateTimeDigitized",
            "ModDate",
            "CreateDate",
            "ModifyDate",
            "MetadataDate",
            "Creation Time",
            "FileModifyDate",
            "FileAccessDate",
            "XMP:CreateDate",
            "XMP:ModifyDate",
            "XMP:MetadataDate",
        ]

        return field in date_fields

    def is_gps_decimal_field(self, field):
        return field in [
            "GPS:GPSLatitude",
            "GPS:GPSLongitude",
            "GPS:LatitudeDecimal",
            "GPS:LongitudeDecimal",
        ]

    def get_gps_target_field(self, field):
        if "Latitude" in field:
            return "GPS:LatitudeDecimal"

        if "Longitude" in field:
            return "GPS:LongitudeDecimal"

        return None

    def on_field_selected(self, event=None):
        field = self.field_var.get()

        if self.is_date_field(field):
            self.open_datetime_editor(field, "")
            return

        if self.is_gps_decimal_field(field):
            self.open_gps_decimal_editor(field, "")
            return

    def open_datetime_editor(self, field_name, current_value):
        window = tk.Toplevel(self.root)
        window.title(f"Edit {field_name}")
        window.geometry("320x220")
        window.resizable(False, False)

        ttk.Label(window, text=f"Edit field: {field_name}").pack(pady=8)

        date_entry = DateEntry(
            window,
            date_pattern="yyyy-mm-dd",
            width=20
        )
        date_entry.pack(pady=5)

        time_frame = ttk.Frame(window)
        time_frame.pack(pady=10)

        ttk.Label(time_frame, text="Hour:").grid(row=0, column=0, padx=5)
        hour_var = tk.StringVar(value="00")
        ttk.Spinbox(
            time_frame,
            from_=0,
            to=23,
            width=5,
            textvariable=hour_var,
            format="%02.0f"
        ).grid(row=0, column=1, padx=5)

        ttk.Label(time_frame, text="Minute:").grid(row=0, column=2, padx=5)
        minute_var = tk.StringVar(value="00")
        ttk.Spinbox(
            time_frame,
            from_=0,
            to=59,
            width=5,
            textvariable=minute_var,
            format="%02.0f"
        ).grid(row=0, column=3, padx=5)

        ttk.Label(time_frame, text="Second:").grid(row=1, column=0, padx=5, pady=8)
        second_var = tk.StringVar(value="00")
        ttk.Spinbox(
            time_frame,
            from_=0,
            to=59,
            width=5,
            textvariable=second_var,
            format="%02.0f"
        ).grid(row=1, column=1, padx=5, pady=8)

        def save_datetime():
            selected_date = date_entry.get_date()

            try:
                hour = int(hour_var.get())
                minute = int(minute_var.get())
                second = int(second_var.get())
            except ValueError:
                messagebox.showerror("Error", "Invalid time value.")
                return

            new_value = (
                f"{selected_date.strftime('%Y-%m-%d')} "
                f"{hour:02d}:{minute:02d}:{second:02d}"
            )

            success = self.handler.edit_metadata(field_name, new_value)

            if success is not False:
                self.refresh_view()
                self.value_entry.delete(0, tk.END)
                window.destroy()
                messagebox.showinfo("Success", f"Updated field: {field_name}")

        ttk.Button(
            window,
            text="Save",
            command=save_datetime
        ).pack(pady=10)

        ttk.Button(
            window,
            text="Cancel",
            command=window.destroy
        ).pack()

    def find_current_gps_decimal_value(self, target_field):
        if not self.handler or not hasattr(self.handler, "get_metadata"):
            return ""

        data = self.handler.get_metadata()
        gps_data = data.get("extended_metadata", {})

        return gps_data.get(target_field, "")

    def open_gps_decimal_editor(self, field_name, current_value):
        window = tk.Toplevel(self.root)
        window.title(f"Edit {field_name}")
        window.geometry("360x180")
        window.resizable(False, False)

        target_field = self.get_gps_target_field(field_name)

        if target_field is None:
            messagebox.showerror("Error", "Unknown GPS field.")
            window.destroy()
            return

        ttk.Label(
            window,
            text=f"Enter decimal value for {target_field}:"
        ).pack(pady=10)

        value_var = tk.StringVar()

        current_decimal_value = self.find_current_gps_decimal_value(target_field)

        if current_decimal_value:
            value_var.set(str(current_decimal_value))

        value_entry = ttk.Entry(window, textvariable=value_var, width=30)
        value_entry.pack(pady=5)
        value_entry.focus_set()

        ttk.Label(
            window,
            text="Examples: 52.2297, 21.0122, -33.8688"
        ).pack(pady=5)

        def save_gps_value():
            value = value_var.get().strip()

            try:
                float(value)
            except ValueError:
                messagebox.showerror("Error", "Invalid GPS decimal value.")
                return

            success = self.handler.edit_metadata(target_field, value)

            if success is not False:
                self.refresh_view()
                self.value_entry.delete(0, tk.END)
                window.destroy()
                messagebox.showinfo("Success", f"Updated field: {target_field}")

        ttk.Button(
            window,
            text="Save",
            command=save_gps_value
        ).pack(pady=10)

        ttk.Button(
            window,
            text="Cancel",
            command=window.destroy
        ).pack()


if __name__ == "__main__":
    root = TkinterDnD.Tk()
    app = MetadataGUI(root)
    root.mainloop()