import os

from handlers.jpg_handler import JPGHandler
from handlers.png_handler import PNGHandler
from handlers.pdf_handler import PDFHandler
from handlers.docx_handler import DOCXHandler
from handlers.exe_handler import EXEHandler


class MetadataManager:
    def __init__(self, working_directory="samples"):
        self.working_directory = working_directory

        self.handlers = {
            ".jpg": JPGHandler,
            ".jpeg": JPGHandler,
            ".png": PNGHandler,
            ".pdf": PDFHandler,
            ".docx": DOCXHandler,
            ".exe": EXEHandler,
        }

    def start(self):
        while True:
            print("\n=== METADATA ANALYSIS TOOL ===")
            print(f"Working directory: {self.working_directory}")
            file_name = input("Enter file name or path, or type 'exit': ").strip()

            if file_name.lower() == "exit":
                print("Exiting...")
                break

            file_path = self._resolve_file_path(file_name)

            if not os.path.exists(file_path):
                print("[!] File does not exist.")
                continue

            extension = os.path.splitext(file_path)[1].lower()

            if extension not in self.handlers:
                print(f"[!] Unsupported file format: {extension}")
                continue

            handler_class = self.handlers[extension]
            handler = handler_class(file_path)

            if handler.read_metadata():
                handler.run_menu()
            else:
                print("[!] Could not read metadata from the selected file.")

    def _resolve_file_path(self, file_name):
        if os.path.isabs(file_name):
            return file_name

        if os.path.exists(file_name):
            return file_name

        return os.path.join(self.working_directory, file_name)