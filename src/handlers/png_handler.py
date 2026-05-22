import os
import xml.etree.ElementTree as ET
from datetime import datetime

from PIL import Image
from PIL.PngImagePlugin import PngInfo


class PNGHandler:
    FILESYSTEM_EDITABLE_FIELDS = [
        "FileModifyDate",
        "FileAccessDate",
    ]

    STANDARD_EDITABLE_FIELDS = [
        "Title",
        "Author",
        "Description",
        "Comment",
        "Software",
        "Source",
        "Creation Time",
        "Disclaimer",
        "Warning",
        "Copyright",
    ]

    def __init__(self, file_path):
        self.file_path = file_path

        self.metadata = {}
        self.file_info = {}
        self.technical_info = {}
        self.text_metadata = {}
        self.xmp_metadata = {}
        self.image_size = (0, 0)

    def read_metadata(self):
        if not os.path.exists(self.file_path):
            return False

        try:
            self.file_info = self._read_file_info()

            with Image.open(self.file_path) as image:
                self.image_size = image.size

                self.technical_info = {
                    "Format": image.format or "",
                    "Mode": image.mode or "",
                    "Width": image.size[0],
                    "Height": image.size[1],
                    "Has transparency": str(self._has_transparency(image)),
                }

                self.text_metadata = {}
                self.xmp_metadata = {}

                for key, value in image.info.items():
                    if key in ["xmp", "XML:com.adobe.xmp"]:
                        continue

                    if isinstance(value, str):
                        self.text_metadata[key] = value
                    else:
                        self.text_metadata[key] = str(value)

                xmp_raw = image.info.get("xmp") or image.info.get("XML:com.adobe.xmp")

                if xmp_raw:
                    self.xmp_metadata = self._parse_xmp(xmp_raw)

            self.metadata = {}
            self.metadata.update(self.file_info)
            self.metadata.update(self.technical_info)
            self.metadata.update(self.text_metadata)
            self.metadata.update(self.xmp_metadata)

            return True

        except Exception as error:
            print(f"[!] PNG read error: {error}")
            return False

    def _read_file_info(self):
        stat = os.stat(self.file_path)

        return {
            "FileName": os.path.basename(self.file_path),
            "FileSize": self._format_file_size(stat.st_size),
            "FileModifyDate": self._format_timestamp(stat.st_mtime),
            "FileAccessDate": self._format_timestamp(stat.st_atime),
            "FileInodeChangeDate": self._format_timestamp(stat.st_ctime),
            "FileType": "PNG",
            "FileTypeExtension": "png",
            "MIMEType": "image/png",
        }

    def _format_file_size(self, size_bytes):
        if size_bytes < 1024:
            return f"{size_bytes} B"

        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} kB"

        return f"{size_bytes / (1024 * 1024):.1f} MB"

    def _format_timestamp(self, timestamp):
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")

    def _parse_datetime(self, value):
        value = str(value).strip()

        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
        ]

        for fmt in formats:
            try:
                parsed = datetime.strptime(value, fmt)

                if fmt == "%Y-%m-%d":
                    parsed = parsed.replace(hour=0, minute=0, second=0)

                return parsed
            except ValueError:
                pass

        try:
            return datetime.fromisoformat(value)
        except ValueError:
            raise ValueError("Invalid date format. Use YYYY-MM-DD HH:MM:SS")

    def _has_transparency(self, image):
        if image.mode in ("RGBA", "LA"):
            return True

        if image.mode == "P" and "transparency" in image.info:
            return True

        return False

    def _parse_xmp(self, xmp_content):
        result = {}

        try:
            if isinstance(xmp_content, bytes):
                xmp_content = xmp_content.decode("utf-8", errors="ignore")

            root = ET.fromstring(xmp_content)

            for element in root.iter():
                tag_name = self._clean_xml_tag(element.tag)

                if element.text and element.text.strip():
                    result[f"XMP:{tag_name}"] = element.text.strip()

                for attr_name, attr_value in element.attrib.items():
                    clean_attr = self._clean_xml_tag(attr_name)
                    result[f"XMP:{tag_name}.{clean_attr}"] = attr_value

        except Exception as error:
            result["XMP:ParsingStatus"] = f"XML parsing error: {error}"

        return result

    def _clean_xml_tag(self, tag):
        return tag.split("}")[-1]

    def get_metadata(self):
        return {
            "file_path": self.file_path,
            "file_name": os.path.basename(self.file_path),
            "statistics": self.file_info,
            "technical_metadata": self.technical_info,
            "editable_metadata": self.text_metadata,
            "extended_metadata": self.xmp_metadata,
            "custom_metadata": {},
            "all_metadata": self.metadata,
        }

    def get_editable_tags(self):
        tags = []

        tags.extend(self.FILESYSTEM_EDITABLE_FIELDS)

        for tag in self.STANDARD_EDITABLE_FIELDS:
            if tag not in tags:
                tags.append(tag)

        for tag in self.text_metadata.keys():
            if tag not in tags:
                tags.append(tag)

        return tags

    def get_tags(self):
        return list(self.metadata.keys())

    def display_metadata(self):
        print("\n" + "=" * 60)
        print(f"  PNG REPORT: {os.path.basename(self.file_path)}")
        print("=" * 60)

        print("[ File Information ]")
        for key, value in self.file_info.items():
            print(f"  > {key:25}: {value}")

        print("\n[ Technical Information ]")
        for key, value in self.technical_info.items():
            print(f"  > {key:25}: {value}")

        print("\n[ PNG Text Metadata ]")
        if not self.text_metadata:
            print("  No PNG text metadata found.")
        else:
            for key, value in self.text_metadata.items():
                print(f"  > {key:25}: {value}")

        print("\n[ XMP Metadata ]")
        if not self.xmp_metadata:
            print("  No XMP metadata found.")
        else:
            for key, value in self.xmp_metadata.items():
                print(f"  > {key:25}: {value}")

        print("=" * 60)

    def edit_metadata(self, tag, value):
        if tag in self.FILESYSTEM_EDITABLE_FIELDS:
            return self.edit_filesystem_metadata(tag, value)

        if tag.startswith("XMP:"):
            print("[!] Direct XMP editing is not enabled for PNG in this version.")
            return False

        return self.edit_text_metadata(tag, value)

    def edit_filesystem_metadata(self, tag, value):
        try:
            parsed_datetime = self._parse_datetime(value)
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

    def edit_text_metadata(self, tag, value):
        try:
            with Image.open(self.file_path) as image:
                png_info = PngInfo()

                for key, old_value in image.info.items():
                    if key in ["xmp", "XML:com.adobe.xmp"]:
                        continue

                    if isinstance(old_value, str):
                        png_info.add_text(key, str(old_value))

                png_info.add_text(tag, str(value))

                image.save(self.file_path, pnginfo=png_info)

            self.read_metadata()
            print(f"[+] Updated PNG text metadata field '{tag}'.")
            return True

        except Exception as error:
            print(f"[!] PNG metadata write error: {error}")
            return False

    def remove_tag(self, tag):
        if tag in self.FILESYSTEM_EDITABLE_FIELDS:
            print("[!] Filesystem timestamps cannot be removed, only modified.")
            return False

        if tag.startswith("XMP:"):
            print("[!] Direct XMP removing is not enabled for PNG in this version.")
            return False

        try:
            with Image.open(self.file_path) as image:
                png_info = PngInfo()

                for key, value in image.info.items():
                    if key in ["xmp", "XML:com.adobe.xmp"]:
                        continue

                    if isinstance(value, str) and key != tag:
                        png_info.add_text(key, str(value))

                image.save(self.file_path, pnginfo=png_info)

            self.read_metadata()
            print(f"[+] Removed PNG text metadata field '{tag}'.")
            return True

        except Exception as error:
            print(f"[!] PNG tag remove error: {error}")
            return False

    def clear_all_editable_metadata(self):
        results = {}

        for tag in list(self.text_metadata.keys()):
            results[tag] = self.remove_tag(tag)

        return results

    def remove_all_metadata(self):
        try:
            with Image.open(self.file_path) as image:
                clean_image = Image.new(image.mode, image.size)
                clean_image.putdata(list(image.getdata()))
                clean_image.save(self.file_path, "PNG")

            self.read_metadata()
            print("[+] Removed all PNG metadata.")
            return True

        except Exception as error:
            print(f"[!] PNG metadata remove error: {error}")
            return False

    def resize_image(self, width, height):
        try:
            with Image.open(self.file_path) as image:
                png_info = PngInfo()

                for key, value in image.info.items():
                    if isinstance(value, str):
                        png_info.add_text(key, str(value))

                resized_image = image.resize((width, height), Image.Resampling.LANCZOS)
                resized_image.save(self.file_path, pnginfo=png_info)

            self.read_metadata()
            print("[+] Image resized.")
            return True

        except Exception as error:
            print(f"[!] PNG resize error: {error}")
            return False