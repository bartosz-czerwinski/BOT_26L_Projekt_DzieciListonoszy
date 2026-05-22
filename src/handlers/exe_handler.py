import os
import datetime
import pefile


class EXEHandler:
    def __init__(self, file_path):
        self.file_path = file_path
        self.metadata = {}
        self.technical_info = {}

    def read_metadata(self):
        if not os.path.exists(self.file_path):
            return False

        try:
            pe = pefile.PE(self.file_path)

            architecture = (
                "x64 (64-bit)"
                if pe.FILE_HEADER.Machine == 0x8664
                else "x86 (32-bit)"
            )

            compile_date = datetime.datetime.fromtimestamp(
                pe.FILE_HEADER.TimeDateStamp
            )

            self.technical_info = {
                "Architecture": architecture,
                "Compile Time": compile_date.strftime("%Y-%m-%d %H:%M:%S"),
                "Section Count": pe.FILE_HEADER.NumberOfSections,
            }

            self.metadata = {}

            if hasattr(pe, "FileInfo"):
                for file_info in pe.FileInfo[0]:
                    if file_info.Key.decode(errors="ignore") == "StringFileInfo":
                        for string_table in file_info.StringTable:
                            for key, value in string_table.entries.items():
                                clean_key = key.decode(errors="ignore")
                                clean_value = value.decode(errors="ignore")
                                self.metadata[clean_key] = clean_value

            return True

        except Exception as error:
            print(f"[!] EXE read error: {error}")
            return False

    def display_metadata(self):
        print("\n" + "=" * 60)
        print(f"  EXE ANALYSIS REPORT: {os.path.basename(self.file_path)}")
        print("=" * 60)

        print("[ PE Header / Technical Information ]")
        for key, value in self.technical_info.items():
            print(f"  > {key:20}: {value}")

        print("\n[ Version Information ]")
        if not self.metadata:
            print("  No version information found.")
        else:
            for key, value in self.metadata.items():
                print(f"  > {key:20}: {value}")

        print("=" * 60)

    def get_tags(self):
        return list(self.metadata.keys())

    def edit_metadata(self, tag, new_value):
        print("\n[!] Editing EXE metadata is disabled.")
        print("    Modifying metadata inside compiled PE files is risky.")
        print("    Changing string length may corrupt the executable.")
        print("    For this project, EXE support is read-only.")

    def remove_tag(self, tag):
        print("\n[!] Removing EXE metadata is disabled.")
        print("    EXE metadata support is read-only in this version.")

    def run_menu(self):
        while True:
            self.display_metadata()

            print("\nEXE OPERATIONS:")
            print("1. Show edit warning")
            print("2. Back")

            choice = input("Choose option: ").strip()

            if choice == "1":
                self.edit_metadata(None, None)

            elif choice == "2":
                break