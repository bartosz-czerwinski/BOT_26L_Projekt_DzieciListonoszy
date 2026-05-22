import os
import shutil
import datetime
import subprocess

import pefile


class EXEHandler:
    FILESYSTEM_EDITABLE_FIELDS = [
        "FileModifyDate",
        "FileAccessDate",
    ]

    PE_EDITABLE_FIELDS = [
        "CompileTime",
        "CheckSum",
        "SignWithCertificate",
    ]

    REMOVABLE_FIELDS = [
        "Overlay",
        "CertificateTable",
        "DebugDirectory",
        "DigitalSignature",
    ]

    def __init__(self, file_path):
        self.file_path = file_path

        self.metadata = {}
        self.file_info = {}
        self.technical_info = {}
        self.version_metadata = {}
        self.section_metadata = {}
        self.import_metadata = {}
        self.security_metadata = {}
        self.extended_metadata = {}

    def _find_rcedit(self):
        project_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )

        possible_paths = [
            os.path.join(project_root, "tools", "rcedit-x64.exe"),
            os.path.join(project_root, "tools", "rcedit.exe"),
            os.path.join(os.getcwd(), "tools", "rcedit-x64.exe"),
            os.path.join(os.getcwd(), "tools", "rcedit.exe"),
            shutil.which("rcedit-x64"),
            shutil.which("rcedit"),
        ]

        for path in possible_paths:
            if path and os.path.exists(path):
                return path

        return None

    def read_metadata(self):
        if not os.path.exists(self.file_path):
            return False

        try:
            pe = pefile.PE(self.file_path, fast_load=False)

            self.file_info = self._read_file_info()
            self.technical_info = self._read_technical_info(pe)
            self.version_metadata = self._read_version_info(pe)
            self.section_metadata = self._read_sections(pe)
            self.import_metadata = self._read_imports(pe)
            self.security_metadata = self._read_security_info(pe)
            self.extended_metadata = self._read_extended_info(pe)

            self.metadata = {}
            self.metadata.update(self.file_info)
            self.metadata.update(self.technical_info)
            self.metadata.update(self.version_metadata)
            self.metadata.update(self.section_metadata)
            self.metadata.update(self.import_metadata)
            self.metadata.update(self.security_metadata)
            self.metadata.update(self.extended_metadata)

            pe.close()
            return True

        except Exception as error:
            print(f"[!] EXE read error: {error}")
            return False

    def _read_file_info(self):
        stat = os.stat(self.file_path)

        return {
            "FileName": os.path.basename(self.file_path),
            "FileSize": self._format_file_size(stat.st_size),
            "FileModifyDate": self._format_timestamp(stat.st_mtime),
            "FileAccessDate": self._format_timestamp(stat.st_atime),
            "FileInodeChangeDate": self._format_timestamp(stat.st_ctime),
            "FileType": "EXE",
            "FileTypeExtension": "exe",
            "MIMEType": "application/vnd.microsoft.portable-executable",
        }

    def _read_technical_info(self, pe):
        machine = pe.FILE_HEADER.Machine

        architecture_map = {
            0x014c: "x86 (32-bit)",
            0x8664: "x64 (64-bit)",
            0x0200: "Intel Itanium",
            0x01c0: "ARM",
            0xaa64: "ARM64",
        }

        subsystem_map = {
            1: "Native",
            2: "Windows GUI",
            3: "Windows CUI",
            5: "OS/2 CUI",
            7: "POSIX CUI",
            9: "Windows CE GUI",
            10: "EFI Application",
            11: "EFI Boot Service Driver",
            12: "EFI Runtime Driver",
            14: "Xbox",
            16: "Windows Boot Application",
        }

        try:
            compile_time = datetime.datetime.fromtimestamp(
                pe.FILE_HEADER.TimeDateStamp
            ).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            compile_time = str(pe.FILE_HEADER.TimeDateStamp)

        return {
            "Architecture": architecture_map.get(machine, f"Unknown ({hex(machine)})"),
            "Machine": hex(machine),
            "CompileTime": compile_time,
            "CompileTimestampRaw": pe.FILE_HEADER.TimeDateStamp,
            "SectionCount": pe.FILE_HEADER.NumberOfSections,
            "Characteristics": hex(pe.FILE_HEADER.Characteristics),
            "EntryPoint": hex(pe.OPTIONAL_HEADER.AddressOfEntryPoint),
            "ImageBase": hex(pe.OPTIONAL_HEADER.ImageBase),
            "Subsystem": subsystem_map.get(
                pe.OPTIONAL_HEADER.Subsystem,
                str(pe.OPTIONAL_HEADER.Subsystem)
            ),
            "CheckSum": hex(pe.OPTIONAL_HEADER.CheckSum),
            "SizeOfImage": pe.OPTIONAL_HEADER.SizeOfImage,
            "SizeOfHeaders": pe.OPTIONAL_HEADER.SizeOfHeaders,
            "DllCharacteristics": hex(pe.OPTIONAL_HEADER.DllCharacteristics),
            "PEType": (
                "PE32+"
                if pe.PE_TYPE == pefile.OPTIONAL_HEADER_MAGIC_PE_PLUS
                else "PE32"
            ),
        }

    def _read_version_info(self, pe):
        result = {}

        if not hasattr(pe, "FileInfo"):
            return result

        try:
            for file_info_list in pe.FileInfo:
                for file_info in file_info_list:
                    key = self._decode_bytes(file_info.Key)

                    if key == "StringFileInfo":
                        for string_table in file_info.StringTable:
                            for raw_key, raw_value in string_table.entries.items():
                                clean_key = self._decode_bytes(raw_key)
                                clean_value = self._decode_bytes(raw_value)
                                result[f"Version:{clean_key}"] = clean_value

                    elif key == "VarFileInfo":
                        for var in file_info.Var:
                            for raw_key, raw_value in var.entry.items():
                                clean_key = self._decode_bytes(raw_key)
                                result[f"Version:{clean_key}"] = str(raw_value)

        except Exception as error:
            result["VersionInfoStatus"] = f"Version info read error: {error}"

        return result

    def _read_sections(self, pe):
        result = {}

        try:
            for index, section in enumerate(pe.sections):
                name = self._decode_bytes(section.Name).strip("\x00")
                prefix = f"Section[{index}]:{name}"

                result[f"{prefix}:VirtualAddress"] = hex(section.VirtualAddress)
                result[f"{prefix}:VirtualSize"] = section.Misc_VirtualSize
                result[f"{prefix}:RawSize"] = section.SizeOfRawData
                result[f"{prefix}:RawPointer"] = hex(section.PointerToRawData)
                result[f"{prefix}:Entropy"] = round(section.get_entropy(), 4)
                result[f"{prefix}:Characteristics"] = hex(section.Characteristics)

        except Exception as error:
            result["SectionStatus"] = f"Section read error: {error}"

        return result

    def _read_imports(self, pe):
        result = {}

        try:
            if not hasattr(pe, "DIRECTORY_ENTRY_IMPORT"):
                return result

            for entry in pe.DIRECTORY_ENTRY_IMPORT:
                dll_name = self._decode_bytes(entry.dll)
                imported_functions = []

                for imported_symbol in entry.imports:
                    if imported_symbol.name:
                        imported_functions.append(
                            self._decode_bytes(imported_symbol.name)
                        )
                    else:
                        imported_functions.append(
                            f"Ordinal:{imported_symbol.ordinal}"
                        )

                result[f"Import:{dll_name}"] = ", ".join(imported_functions[:50])

                if len(imported_functions) > 50:
                    result[f"Import:{dll_name}:Truncated"] = (
                        f"Displayed 50 of {len(imported_functions)} imports"
                    )

        except Exception as error:
            result["ImportStatus"] = f"Import read error: {error}"

        return result

    def _read_security_info(self, pe):
        result = {}

        try:
            security_index = pefile.DIRECTORY_ENTRY[
                "IMAGE_DIRECTORY_ENTRY_SECURITY"
            ]
            security_directory = pe.OPTIONAL_HEADER.DATA_DIRECTORY[
                security_index
            ]

            result["CertificateTable:VirtualAddress"] = hex(
                security_directory.VirtualAddress
            )
            result["CertificateTable:Size"] = security_directory.Size
            result["HasCertificateTable"] = str(security_directory.Size > 0)

            debug_index = pefile.DIRECTORY_ENTRY[
                "IMAGE_DIRECTORY_ENTRY_DEBUG"
            ]
            debug_directory = pe.OPTIONAL_HEADER.DATA_DIRECTORY[
                debug_index
            ]

            result["DebugDirectory:VirtualAddress"] = hex(
                debug_directory.VirtualAddress
            )
            result["DebugDirectory:Size"] = debug_directory.Size
            result["HasDebugDirectory"] = str(debug_directory.Size > 0)

            overlay = pe.get_overlay()
            result["HasOverlay"] = str(bool(overlay))
            result["OverlaySize"] = len(overlay) if overlay else 0

        except Exception as error:
            result["SecurityInfoStatus"] = f"Security info read error: {error}"

        return result

    def _read_extended_info(self, pe):
        result = {}

        try:
            if hasattr(pe, "DIRECTORY_ENTRY_EXPORT"):
                exports = []

                for exported_symbol in pe.DIRECTORY_ENTRY_EXPORT.symbols:
                    if exported_symbol.name:
                        exports.append(self._decode_bytes(exported_symbol.name))
                    else:
                        exports.append(f"Ordinal:{exported_symbol.ordinal}")

                result["Exports"] = ", ".join(exports[:50])

            try:
                if hasattr(pe, "DIRECTORY_ENTRY_RESOURCE"):
                    result["ResourceEntries"] = len(
                        pe.DIRECTORY_ENTRY_RESOURCE.entries
                    )
            except Exception:
                pass

            try:
                if hasattr(pe, "DIRECTORY_ENTRY_TLS"):
                    result["HasTLS"] = "True"
            except Exception:
                pass

            try:
                if hasattr(pe, "DIRECTORY_ENTRY_LOAD_CONFIG"):
                    result["HasLoadConfig"] = "True"
            except Exception:
                pass

            try:
                rich_header = getattr(pe, "RICH_HEADER", None)

                if rich_header:
                    result["HasRichHeader"] = "True"

                    if hasattr(rich_header, "checksum"):
                        result["RichHeaderChecksum"] = hex(
                            rich_header.checksum
                        )
            except Exception:
                result["HasRichHeader"] = "Unreadable"

        except Exception as error:
            result["ExtendedInfoStatus"] = f"Extended info read error: {error}"

        return result

    def get_metadata(self):
        return {
            "file_path": self.file_path,
            "file_name": os.path.basename(self.file_path),
            "statistics": self.file_info,
            "technical_metadata": self.technical_info,
            "editable_metadata": self.version_metadata,
            "extended_metadata": {
                **self.section_metadata,
                **self.import_metadata,
                **self.security_metadata,
                **self.extended_metadata,
            },
            "custom_metadata": {},
            "all_metadata": self.metadata,
        }

    def get_editable_tags(self):
        tags = []

        tags.extend(self.FILESYSTEM_EDITABLE_FIELDS)
        tags.extend(self.PE_EDITABLE_FIELDS)

        for key in self.version_metadata.keys():
            if key.startswith("Version:"):
                tags.append(key)

        default_version_fields = [
            "Version:CompanyName",
            "Version:FileDescription",
            "Version:FileVersion",
            "Version:InternalName",
            "Version:LegalCopyright",
            "Version:OriginalFilename",
            "Version:ProductName",
            "Version:ProductVersion",
        ]

        for field in default_version_fields:
            if field not in tags:
                tags.append(field)

        tags.extend(self.REMOVABLE_FIELDS)

        return tags

    def get_tags(self):
        return list(self.metadata.keys())

    def edit_metadata(self, tag, new_value):
        if tag in self.FILESYSTEM_EDITABLE_FIELDS:
            return self.edit_filesystem_metadata(tag, new_value)

        if tag == "CompileTime":
            return self.edit_compile_time(new_value)

        if tag == "CheckSum":
            return self.recalculate_checksum()
        
        if tag == "SignWithCertificate":
            parts = str(new_value).split(";", 1)
            cert_path = parts[0].strip()
            cert_password = parts[1].strip() if len(parts) > 1 else ""
            return self.sign_exe(cert_path, cert_password)

        if tag.startswith("Version:"):
            version_key = tag.replace("Version:", "", 1)
            return self.edit_version_string(version_key, new_value)

        print(f"[!] Field '{tag}' is not editable for EXE.")
        return False

    def edit_filesystem_metadata(self, tag, new_value):
        try:
            parsed_datetime = self._parse_datetime(new_value)
            new_timestamp = parsed_datetime.timestamp()

            stat = os.stat(self.file_path)
            current_access_time = stat.st_atime
            current_modify_time = stat.st_mtime

            if tag == "FileModifyDate":
                os.utime(self.file_path, (current_access_time, new_timestamp))

            elif tag == "FileAccessDate":
                os.utime(self.file_path, (new_timestamp, current_modify_time))

            else:
                print(f"[!] Filesystem field '{tag}' is not editable.")
                return False

            self.read_metadata()
            print(f"[+] Updated filesystem field '{tag}'.")
            return True

        except Exception as error:
            print(f"[!] Filesystem metadata write error: {error}")
            return False

    def edit_compile_time(self, new_value):
        try:
            parsed_datetime = self._parse_datetime(new_value)
            timestamp = int(parsed_datetime.timestamp())

            pe = pefile.PE(self.file_path)
            pe.FILE_HEADER.TimeDateStamp = timestamp

            new_data = pe.write()
            pe.close()

            with open(self.file_path, "wb") as file:
                file.write(new_data)

            self.read_metadata()
            print("[+] Updated PE compile timestamp.")
            return True

        except Exception as error:
            print(f"[!] Compile timestamp write error: {error}")
            return False

    def recalculate_checksum(self):
        try:
            pe = pefile.PE(self.file_path)
            pe.OPTIONAL_HEADER.CheckSum = pe.generate_checksum()

            new_data = pe.write()
            pe.close()

            with open(self.file_path, "wb") as file:
                file.write(new_data)

            self.read_metadata()
            print("[+] Recalculated PE checksum.")
            return True

        except Exception as error:
            print(f"[!] Checksum update error: {error}")
            return False

    def edit_version_string(self, version_key, new_value):
        try:
            rcedit_path = self._find_rcedit()

            if rcedit_path is None:
                print("[!] rcedit.exe was not found.")
                print("    Download rcedit-x64.exe and put it in tools/rcedit-x64.exe")
                return False

            supported_fields = {
                "CompanyName",
                "FileDescription",
                "FileVersion",
                "InternalName",
                "LegalCopyright",
                "OriginalFilename",
                "ProductName",
                "ProductVersion",
            }

            if version_key not in supported_fields:
                print(f"[!] Field '{version_key}' is not supported by rcedit.")
                return False

            original_overlay = self._get_overlay_bytes()

            command = [
                rcedit_path,
                self.file_path,
                "--set-version-string",
                version_key,
                str(new_value),
            ]

            result = subprocess.run(command, capture_output=True, text=True)

            if result.returncode != 0:
                print("[!] rcedit write error:")
                print(result.stderr.strip())
                return False

            self._restore_overlay_if_missing(original_overlay)

            self.read_metadata()

            print(f"[+] Updated version field '{version_key}' using rcedit.")
            return True

        except Exception as error:
            print(f"[!] Version resource write error: {error}")
            return False
        
    def _get_overlay_bytes(self):
        try:
            pe = pefile.PE(self.file_path)
            overlay = pe.get_overlay()
            pe.close()
            return overlay
        except Exception:
            return None


    def _restore_overlay_if_missing(self, original_overlay):
        if not original_overlay:
            return

        try:
            pe = pefile.PE(self.file_path)
            current_overlay = pe.get_overlay()
            pe.close()

            if current_overlay:
                return

            with open(self.file_path, "ab") as file:
                file.write(original_overlay)

            print("[+] Restored original EXE overlay.")

        except Exception as error:
            print(f"[!] Overlay restore warning: {error}")

    def remove_tag(self, tag):
        if tag in self.FILESYSTEM_EDITABLE_FIELDS:
            print("[!] Filesystem timestamps cannot be removed, only modified.")
            return False

        if tag == "Overlay":
            return self.remove_overlay()

        if tag == "CertificateTable":
            return self.remove_certificate_table()

        if tag == "DebugDirectory":
            return self.remove_debug_directory()

        if tag == "DigitalSignature":
            return self.remove_certificate_table() 

        if tag.startswith("Version:"):
            return self.edit_metadata(tag, "")
        
 

        print(f"[!] Removing field '{tag}' is not supported.")
        return False

    def remove_overlay(self):
        try:
            pe = pefile.PE(self.file_path)
            overlay_offset = pe.get_overlay_data_start_offset()

            if overlay_offset is None:
                print("[!] No overlay found.")
                pe.close()
                return False

            with open(self.file_path, "rb") as file:
                data = file.read()

            pe.close()

            with open(self.file_path, "wb") as file:
                file.write(data[:overlay_offset])

            self.read_metadata()

            print("[+] Removed PE overlay.")
            return True

        except Exception as error:
            print(f"[!] Overlay remove error: {error}")
            return False

    def remove_certificate_table(self):
        try:
            pe = pefile.PE(self.file_path)

            security_index = pefile.DIRECTORY_ENTRY[
                "IMAGE_DIRECTORY_ENTRY_SECURITY"
            ]
            security_directory = pe.OPTIONAL_HEADER.DATA_DIRECTORY[
                security_index
            ]

            cert_offset = security_directory.VirtualAddress
            cert_size = security_directory.Size

            if cert_offset == 0 or cert_size == 0:
                print("[!] No digital signature found.")
                pe.close()
                return False

            with open(self.file_path, "rb") as file:
                data = file.read()

            security_directory.VirtualAddress = 0
            security_directory.Size = 0

            patched_data = pe.write()
            pe.close()

            # certificate table jest na końcu/overlay area, więc odcinamy tylko podpis
            if cert_offset + cert_size <= len(data):
                final_data = patched_data[:cert_offset] + data[cert_offset + cert_size:]
            else:
                final_data = patched_data

            with open(self.file_path, "wb") as file:
                file.write(final_data)

            self.read_metadata()
            print("[+] Removed digital signature / certificate table.")
            return True

        except Exception as error:
            print(f"[!] Digital signature remove error: {error}")
            return False

    def remove_debug_directory(self):
        try:
            pe = pefile.PE(self.file_path)

            debug_index = pefile.DIRECTORY_ENTRY[
                "IMAGE_DIRECTORY_ENTRY_DEBUG"
            ]
            debug_directory = pe.OPTIONAL_HEADER.DATA_DIRECTORY[
                debug_index
            ]

            if debug_directory.VirtualAddress == 0 or debug_directory.Size == 0:
                print("[!] No debug directory found.")
                pe.close()
                return False

            debug_directory.VirtualAddress = 0
            debug_directory.Size = 0

            new_data = pe.write()
            pe.close()

            with open(self.file_path, "wb") as file:
                file.write(new_data)

            self.read_metadata()

            print("[+] Removed debug directory reference.")
            return True

        except Exception as error:
            print(f"[!] Debug directory remove error: {error}")
            return False
        
    def _find_signtool(self):
        project_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )

        possible_paths = [
            os.path.join(project_root, "tools", "signtool.exe"),
            os.path.join(os.getcwd(), "tools", "signtool.exe"),
            shutil.which("signtool"),
        ]

        for path in possible_paths:
            if path and os.path.exists(path):
                return path

        return None
        
    def sign_exe(self, certificate_path, certificate_password=""):

        try:
            self.remove_certificate_table()
        except Exception:
            pass

        signtool_path = self._find_signtool()

        if signtool_path is None:
            print("[!] signtool.exe was not found in PATH.")
            return False

        command = [
            signtool_path,
            "sign",
            "/f",
            certificate_path,
            "/fd",
            "SHA256",
            "/tr",
            "http://timestamp.digicert.com",
            "/td",
            "SHA256",
        ]

        if certificate_password:
            command.extend(["/p", certificate_password])

        command.append(self.file_path)

        result = subprocess.run(
            command,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print("[!] signtool error:")
            print(result.stderr.strip())
            return False

        self.read_metadata()
        print("[+] EXE signed successfully.")
        return True

    def clear_all_editable_metadata(self):
        results = {}

        for tag in list(self.get_editable_tags()):
            if tag in [
                "FileModifyDate",
                "FileAccessDate",
                "CompileTime",
                "CheckSum",
            ]:
                continue

            results[tag] = self.remove_tag(tag)

        return results

    def save_copy(self, output_path):
        try:
            shutil.copy2(self.file_path, output_path)
            print(f"[+] Saved copy: {output_path}")
            return True

        except Exception as error:
            print(f"[!] Save copy error: {error}")
            return False

    def display_metadata(self):
        print("\n" + "=" * 60)
        print(f"  EXE REPORT: {os.path.basename(self.file_path)}")
        print("=" * 60)

        print("[ File Information ]")
        for key, value in self.file_info.items():
            print(f"  > {key:30}: {value}")

        print("\n[ PE Technical Information ]")
        for key, value in self.technical_info.items():
            print(f"  > {key:30}: {value}")

        print("\n[ Version Information ]")
        if not self.version_metadata:
            print("  No version metadata found.")
        else:
            for key, value in self.version_metadata.items():
                print(f"  > {key:30}: {value}")

        print("\n[ Sections ]")
        for key, value in self.section_metadata.items():
            print(f"  > {key:30}: {value}")

        print("\n[ Imports ]")
        for key, value in self.import_metadata.items():
            print(f"  > {key:30}: {value}")

        print("\n[ Security / Overlay ]")
        for key, value in self.security_metadata.items():
            print(f"  > {key:30}: {value}")

        print("\n[ Extended Information ]")
        for key, value in self.extended_metadata.items():
            print(f"  > {key:30}: {value}")

        print("=" * 60)

    def run_menu(self):
        while True:
            self.display_metadata()

            print("\nEXE OPERATIONS:")
            print("1. Edit metadata")
            print("2. Remove metadata")
            print("3. Recalculate checksum")
            print("4. Save copy")
            print("5. Back")

            choice = input("Choose option: ").strip()

            if choice == "1":
                print("\nEditable fields:")
                for tag in self.get_editable_tags():
                    print(f" - {tag}")

                tag = input("Field name: ").strip()
                value = input("New value: ").strip()
                self.edit_metadata(tag, value)

            elif choice == "2":
                print("\nRemovable fields:")
                for tag in self.REMOVABLE_FIELDS:
                    print(f" - {tag}")

                print("Version fields can also be cleared with their full name, e.g. Version:CompanyName")

                tag = input("Field name: ").strip()
                self.remove_tag(tag)

            elif choice == "3":
                self.recalculate_checksum()

            elif choice == "4":
                output_path = input("Output path: ").strip()
                self.save_copy(output_path)

            elif choice == "5":
                break

    def _format_file_size(self, size_bytes):
        if size_bytes < 1024:
            return f"{size_bytes} B"

        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} kB"

        return f"{size_bytes / (1024 * 1024):.1f} MB"

    def _format_timestamp(self, timestamp):
        return datetime.datetime.fromtimestamp(timestamp).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    def _parse_datetime(self, value):
        value = str(value).strip()

        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
        ]

        for fmt in formats:
            try:
                parsed = datetime.datetime.strptime(value, fmt)

                if fmt == "%Y-%m-%d":
                    parsed = parsed.replace(hour=0, minute=0, second=0)

                return parsed

            except ValueError:
                pass

        try:
            return datetime.datetime.fromisoformat(value)
        except ValueError:
            raise ValueError("Invalid date format. Use YYYY-MM-DD HH:MM:SS")

    def _decode_bytes(self, value):
        if value is None:
            return ""

        if isinstance(value, bytes):
            encodings = ["utf-8", "utf-16le", "latin-1"]

            for encoding in encodings:
                try:
                    return value.decode(encoding, errors="ignore").strip("\x00")
                except Exception:
                    pass

            return str(value)

        return str(value).strip("\x00")