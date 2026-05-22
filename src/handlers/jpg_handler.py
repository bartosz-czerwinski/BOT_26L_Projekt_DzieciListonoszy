import os
from datetime import datetime

from PIL import Image, ExifTags
import piexif


class JPGHandler:
    FILESYSTEM_EDITABLE_FIELDS = [
        "FileModifyDate",
        "FileAccessDate",
    ]

    STANDARD_EDITABLE_FIELDS = [
        "Make",
        "Model",
        "Software",
        "Artist",
        "Copyright",
        "ImageDescription",
        "DateTime",
        "DateTimeOriginal",
        "DateTimeDigitized",
        "UserComment",
    ]

    EXIF_SECTIONS = ["0th", "Exif", "GPS", "Interop", "1st"]

    def __init__(self, file_path):
        self.file_path = file_path

        self.metadata = {}
        self.file_info = {}
        self.technical_info = {}
        self.exif_metadata = {}
        self.gps_metadata = {}
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
                    "ColorSpace": self._format_value(image.info.get("jfif", "")),
                    "DPI": self._format_value(image.info.get("dpi", "")),
                    "Progressive": self._format_value(image.info.get("progression", "")),
                }

            self.exif_metadata = self._read_exif_metadata()
            self.gps_metadata = self._read_gps_metadata()

            self.metadata = {}
            self.metadata.update(self.file_info)
            self.metadata.update(self.technical_info)
            self.metadata.update(self.exif_metadata)
            self.metadata.update(self.gps_metadata)

            return True

        except Exception as error:
            print(f"[!] JPG read error: {error}")
            return False

    def _read_file_info(self):
        stat = os.stat(self.file_path)

        return {
            "FileName": os.path.basename(self.file_path),
            "FileSize": self._format_file_size(stat.st_size),
            "FileModifyDate": self._format_timestamp(stat.st_mtime),
            "FileAccessDate": self._format_timestamp(stat.st_atime),
            "FileInodeChangeDate": self._format_timestamp(stat.st_ctime),
            "FileType": "JPEG",
            "FileTypeExtension": "jpg",
            "MIMEType": "image/jpeg",
        }

    def _read_exif_metadata(self):
        result = {}

        try:
            exif_dict = piexif.load(self.file_path)

            for section in self.EXIF_SECTIONS:
                section_data = exif_dict.get(section, {})

                if not isinstance(section_data, dict):
                    continue

                for tag_id, value in section_data.items():
                    tag_name = self._get_exif_tag_name(section, tag_id)

                    if section == "GPS":
                        continue

                    result[tag_name] = self._format_exif_value(value)

        except Exception as error:
            result["EXIFStatus"] = f"EXIF read error: {error}"

        return result

    def _read_gps_metadata(self):
        result = {}

        try:
            exif_dict = piexif.load(self.file_path)
            gps_data = exif_dict.get("GPS", {})

            if not gps_data:
                return result

            for tag_id, value in gps_data.items():
                tag_name = self._get_exif_tag_name("GPS", tag_id)
                result[f"GPS:{tag_name}"] = self._format_exif_value(value)

            latitude = self._convert_gps_to_decimal(
                gps_data.get(piexif.GPSIFD.GPSLatitude),
                gps_data.get(piexif.GPSIFD.GPSLatitudeRef),
            )

            longitude = self._convert_gps_to_decimal(
                gps_data.get(piexif.GPSIFD.GPSLongitude),
                gps_data.get(piexif.GPSIFD.GPSLongitudeRef),
            )

            if latitude is not None:
                result["GPS:LatitudeDecimal"] = latitude

            if longitude is not None:
                result["GPS:LongitudeDecimal"] = longitude

        except Exception as error:
            result["GPSStatus"] = f"GPS read error: {error}"

        return result

    def _get_exif_tag_name(self, section, tag_id):
        try:
            if section == "GPS":
                return piexif.TAGS["GPS"][tag_id]["name"]

            return piexif.TAGS[section][tag_id]["name"]

        except Exception:
            return str(tag_id)

    def _format_exif_value(self, value):
        if value is None:
            return ""

        if isinstance(value, bytes):
            try:
                return value.decode("utf-8", errors="ignore").strip("\x00")
            except Exception:
                return str(value)

        if isinstance(value, tuple):
            return str(value)

        return str(value)

    def _format_value(self, value):
        if value is None:
            return ""

        return str(value)

    def _convert_gps_to_decimal(self, coordinates, reference):
        if not coordinates or not reference:
            return None

        try:
            degrees = self._rational_to_float(coordinates[0])
            minutes = self._rational_to_float(coordinates[1])
            seconds = self._rational_to_float(coordinates[2])

            decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)

            if isinstance(reference, bytes):
                reference = reference.decode(errors="ignore")

            if reference in ["S", "W"]:
                decimal = -decimal

            return round(decimal, 6)

        except Exception:
            return None

    def _rational_to_float(self, value):
        if isinstance(value, tuple) and len(value) == 2:
            numerator, denominator = value
            if denominator == 0:
                return 0
            return numerator / denominator

        return float(value)

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

    def get_metadata(self):
        return {
            "file_path": self.file_path,
            "file_name": os.path.basename(self.file_path),
            "statistics": self.file_info,
            "technical_metadata": self.technical_info,
            "editable_metadata": self.exif_metadata,
            "extended_metadata": self.gps_metadata,
            "custom_metadata": {},
            "all_metadata": self.metadata,
        }

    def get_editable_tags(self):
        tags = []

        tags.extend(self.FILESYSTEM_EDITABLE_FIELDS)

        for tag in self.STANDARD_EDITABLE_FIELDS:
            if tag not in tags:
                tags.append(tag)

        for tag in self.exif_metadata.keys():
            if tag not in tags:
                tags.append(tag)
        for tag in ["GPS:LatitudeDecimal", "GPS:LongitudeDecimal"]:
            if tag not in tags:
                tags.append(tag)

        return tags

    def get_tags(self):
        return list(self.metadata.keys())

    def display_metadata(self):
        print("\n" + "=" * 60)
        print(f"  JPG REPORT: {os.path.basename(self.file_path)}")
        print("=" * 60)

        print("[ File Information ]")
        for key, value in self.file_info.items():
            print(f"  > {key:25}: {value}")

        print("\n[ Technical Information ]")
        for key, value in self.technical_info.items():
            print(f"  > {key:25}: {value}")

        print("\n[ EXIF Metadata ]")
        if not self.exif_metadata:
            print("  No EXIF metadata found.")
        else:
            for key, value in self.exif_metadata.items():
                print(f"  > {key:25}: {value}")

        print("\n[ GPS Metadata ]")
        if not self.gps_metadata:
            print("  No GPS metadata found.")
        else:
            for key, value in self.gps_metadata.items():
                print(f"  > {key:25}: {value}")

        print("=" * 60)

    def edit_metadata(self, tag, new_value):
        if tag in self.FILESYSTEM_EDITABLE_FIELDS:
            return self.edit_filesystem_metadata(tag, new_value)

        if tag == "GPS:LatitudeDecimal":
            return self.edit_gps_decimal(latitude=float(new_value), longitude=None)

        if tag == "GPS:LongitudeDecimal":
            return self.edit_gps_decimal(latitude=None, longitude=float(new_value))

        if tag.startswith("GPS:"):
            print("[!] Edit GPS using GPS:LatitudeDecimal or GPS:LongitudeDecimal.")
            return False

        return self.edit_exif_metadata(tag, new_value)
    
    def edit_gps_decimal(self, latitude=None, longitude=None):
        try:
            exif_dict = piexif.load(self.file_path)

            if "GPS" not in exif_dict or exif_dict["GPS"] is None:
                exif_dict["GPS"] = {}

            gps = exif_dict["GPS"]

            if latitude is not None:
                gps[piexif.GPSIFD.GPSLatitudeRef] = b"N" if latitude >= 0 else b"S"
                gps[piexif.GPSIFD.GPSLatitude] = self._decimal_to_gps_rational(abs(latitude))

            if longitude is not None:
                gps[piexif.GPSIFD.GPSLongitudeRef] = b"E" if longitude >= 0 else b"W"
                gps[piexif.GPSIFD.GPSLongitude] = self._decimal_to_gps_rational(abs(longitude))

            exif_bytes = piexif.dump(exif_dict)

            with Image.open(self.file_path) as image:
                image.save(self.file_path, "JPEG", exif=exif_bytes)

            self.read_metadata()
            print("[+] Updated GPS coordinates.")
            return True

        except Exception as error:
            print(f"[!] GPS write error: {error}")
            return False

    def _decimal_to_gps_rational(self, decimal_value):
        degrees = int(decimal_value)
        minutes_float = (decimal_value - degrees) * 60
        minutes = int(minutes_float)
        seconds = (minutes_float - minutes) * 60

        return (
            (degrees, 1),
            (minutes, 1),
            (int(seconds * 10000000), 10000000),
        )

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

    def edit_exif_metadata(self, tag_name, new_value):
        try:
            exif_dict = piexif.load(self.file_path)
            tag_info = self._find_exif_tag(tag_name)

            if tag_info is None:
                print(f"[!] Unknown EXIF tag: {tag_name}")
                return False

            section, tag_id = tag_info
            converted_value = self._convert_exif_value(tag_name, new_value)

            exif_dict[section][tag_id] = converted_value
            exif_bytes = piexif.dump(exif_dict)

            with Image.open(self.file_path) as image:
                image.save(self.file_path, "JPEG", exif=exif_bytes)

            self.read_metadata()
            print(f"[+] Updated EXIF tag '{tag_name}'.")
            return True

        except Exception as error:
            print(f"[!] JPG EXIF write error: {error}")
            return False

    def _find_exif_tag(self, tag_name):
        for section in ["0th", "Exif"]:
            for tag_id, tag_data in piexif.TAGS[section].items():
                if tag_data["name"] == tag_name:
                    return section, tag_id

        return None

    def _convert_exif_value(self, tag_name, value):
        value = str(value)

        ascii_fields = {
            "Make",
            "Model",
            "Software",
            "Artist",
            "Copyright",
            "ImageDescription",
            "DateTime",
            "DateTimeOriginal",
            "DateTimeDigitized",
            "UserComment",
        }

        if tag_name in ["DateTime", "DateTimeOriginal", "DateTimeDigitized"]:
            parsed = self._parse_datetime(value)
            value = parsed.strftime("%Y:%m:%d %H:%M:%S")

        if tag_name in ascii_fields:
            return value.encode("utf-8")

        return value.encode("utf-8")

    def remove_tag(self, tag_name):
        if tag_name in self.FILESYSTEM_EDITABLE_FIELDS:
            print("[!] Filesystem timestamps cannot be removed, only modified.")
            return False

        if tag_name.startswith("GPS:"):
            print("[!] Direct GPS removing is not enabled in this version.")
            return False

        try:
            exif_dict = piexif.load(self.file_path)
            tag_info = self._find_exif_tag(tag_name)

            if tag_info is None:
                print(f"[!] Unknown EXIF tag: {tag_name}")
                return False

            section, tag_id = tag_info

            if tag_id in exif_dict.get(section, {}):
                del exif_dict[section][tag_id]

            exif_bytes = piexif.dump(exif_dict)

            with Image.open(self.file_path) as image:
                image.save(self.file_path, "JPEG", exif=exif_bytes)

            self.read_metadata()
            print(f"[+] Removed EXIF tag '{tag_name}'.")
            return True

        except Exception as error:
            print(f"[!] JPG tag remove error: {error}")
            return False

    def clear_all_editable_metadata(self):
        results = {}

        for tag in list(self.exif_metadata.keys()):
            results[tag] = self.remove_tag(tag)

        return results

    def remove_all_metadata(self):
        try:
            with Image.open(self.file_path) as image:
                clean_image = Image.new(image.mode, image.size)
                clean_image.putdata(list(image.getdata()))
                clean_image.save(self.file_path, "JPEG")

            self.read_metadata()
            print("[+] Removed all JPG EXIF metadata.")
            return True

        except Exception as error:
            print(f"[!] JPG metadata remove error: {error}")
            return False

    def resize_image(self, width, height):
        try:
            with Image.open(self.file_path) as image:
                exif = image.info.get("exif")
                resized_image = image.resize((width, height), Image.Resampling.LANCZOS)

                if exif:
                    resized_image.save(self.file_path, "JPEG", exif=exif)
                else:
                    resized_image.save(self.file_path, "JPEG")

            self.read_metadata()
            print("[+] Image resized.")
            return True

        except Exception as error:
            print(f"[!] JPG resize error: {error}")
            return False