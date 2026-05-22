import os
from datetime import datetime
from pypdf import PdfReader

try:
    import pikepdf
except ImportError:
    pikepdf = None


class PDFHandler:
    FILESYSTEM_EDITABLE_FIELDS = [
        "FileModifyDate",
        "FileAccessDate",
    ]

    STANDARD_EDITABLE_FIELDS = [
        "Title",
        "Author",
        "Subject",
        "Keywords",
        "Creator",
        "Producer",
        "CreationDate",
        "ModDate",
        "Company",
        "SourceModified",
    ]

    XMP_NAME_MAP = {
        "{http://ns.adobe.com/pdf/1.3/}Producer": "Producer",
        "{http://ns.adobe.com/pdfx/1.3/}Company": "Company",
        "{http://ns.adobe.com/pdfx/1.3/}SourceModified": "SourceModified",
        "{http://ns.adobe.com/xap/1.0/}CreatorTool": "CreatorTool",
        "{http://ns.adobe.com/xap/1.0/}ModifyDate": "ModifyDate",
        "{http://ns.adobe.com/xap/1.0/}CreateDate": "CreateDate",
        "{http://ns.adobe.com/xap/1.0/}MetadataDate": "MetadataDate",
        "{http://ns.adobe.com/xap/1.0/mm/}DocumentID": "DocumentID",
        "{http://ns.adobe.com/xap/1.0/mm/}InstanceID": "InstanceID",
        "{http://ns.adobe.com/xap/1.0/mm/}VersionID": "VersionID",
        "{http://purl.org/dc/elements/1.1/}format": "Format",
        "{http://purl.org/dc/elements/1.1/}title": "Title",
        "{http://purl.org/dc/elements/1.1/}creator": "Creator",
        "{http://ns.adobe.com/photoshop/1.0/}headline": "Headline",
    }

    def __init__(self, file_path):
        self.file_path = file_path

        self.metadata = {}
        self.file_info = {}
        self.technical_info = {}
        self.document_metadata = {}
        self.xmp_metadata = {}

    def read_metadata(self):
        if not os.path.exists(self.file_path):
            return False

        try:
            reader = PdfReader(self.file_path)

            self.file_info = self._read_file_info()
            self.technical_info = self._read_technical_info(reader)
            self.document_metadata = self._read_document_metadata(reader)
            self.xmp_metadata = self._read_xmp_metadata()

            self.metadata = {}
            self.metadata.update(self.file_info)
            self.metadata.update(self.technical_info)
            self.metadata.update(self.document_metadata)
            self.metadata.update(self.xmp_metadata)

            return True

        except Exception as error:
            print(f"[!] PDF read error: {error}")
            return False

    def _read_file_info(self):
        stat = os.stat(self.file_path)

        return {
            "FileName": os.path.basename(self.file_path),
            "FileSize": self._format_file_size(stat.st_size),
            "FileModifyDate": self._format_timestamp(stat.st_mtime),
            "FileAccessDate": self._format_timestamp(stat.st_atime),
            "FileInodeChangeDate": self._format_timestamp(stat.st_ctime),
            "FileType": "PDF",
            "FileTypeExtension": "pdf",
            "MIMEType": "application/pdf",
        }

    def _read_technical_info(self, reader):
        info = {
            "PDFVersion": self._get_pdf_version(),
            "PageCount": len(reader.pages),
            "Encrypted": str(reader.is_encrypted),
        }

        try:
            trailer = reader.trailer
            root = trailer.get("/Root", {})

            if "/PageLayout" in root:
                info["PageLayout"] = str(root["/PageLayout"]).replace("/", "")

            if "/Lang" in root:
                info["Language"] = str(root["/Lang"])

            if "/MarkInfo" in root:
                mark_info = root["/MarkInfo"]
                if "/Marked" in mark_info:
                    info["TaggedPDF"] = str(mark_info["/Marked"])

        except Exception:
            pass

        return info

    def _read_document_metadata(self, reader):
        result = {}

        if reader.metadata:
            for key, value in reader.metadata.items():
                clean_key = key.replace("/", "")
                result[clean_key] = self._format_pdf_value(clean_key, value)

        return result

    def _read_xmp_metadata(self):
        result = {}

        if pikepdf is None:
            result["XMPStatus"] = "pikepdf not installed"
            return result

        try:
            with pikepdf.open(self.file_path) as pdf:
                with pdf.open_metadata() as metadata:
                    for key, value in metadata.items():
                        clean_key = self.XMP_NAME_MAP.get(str(key), str(key))
                        result[f"XMP:{clean_key}"] = self._format_pdf_value(clean_key, value)

        except Exception as error:
            result["XMPStatus"] = f"XMP read error: {error}"

        return result

    def _get_pdf_version(self):
        try:
            with open(self.file_path, "rb") as file:
                header = file.readline().decode(errors="ignore").strip()

            if header.startswith("%PDF-"):
                return header.replace("%PDF-", "")

        except Exception:
            pass

        return ""

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
            raise ValueError(
                "Invalid date format. Use YYYY-MM-DD HH:MM:SS"
            )

    def _format_pdf_value(self, key, value):
        if value is None:
            return ""

        value = str(value)

        if key in [
            "CreationDate",
            "ModDate",
            "CreateDate",
            "ModifyDate",
            "MetadataDate",
        ]:
            return self._normalize_pdf_date(value)

        return value

    def _normalize_pdf_date(self, value):
        if not value:
            return ""

        if value.startswith("D:"):
            value = value[2:]

        value = value.replace("'", "")

        try:
            year = value[0:4]
            month = value[4:6]
            day = value[6:8]
            hour = value[8:10] or "00"
            minute = value[10:12] or "00"
            second = value[12:14] or "00"

            timezone = ""
            if len(value) > 14:
                timezone = value[14:]
                if len(timezone) >= 5 and timezone[0] in ["+", "-"]:
                    timezone = f"{timezone[0:3]}:{timezone[3:5]}"

            return f"{year}-{month}-{day} {hour}:{minute}:{second}{timezone}"

        except Exception:
            return value

    def get_metadata(self):
        return {
            "file_path": self.file_path,
            "file_name": os.path.basename(self.file_path),
            "statistics": self.file_info,
            "technical_metadata": self.technical_info,
            "editable_metadata": self.document_metadata,
            "extended_metadata": self.xmp_metadata,
            "custom_metadata": {},
            "all_metadata": self.metadata,
        }

    def get_editable_tags(self):
        tags = []

        tags.extend(self.FILESYSTEM_EDITABLE_FIELDS)
        tags.extend(self.STANDARD_EDITABLE_FIELDS)

        for key in self.xmp_metadata.keys():
            clean_key = key.replace("XMP:", "", 1)

            if clean_key in self.XMP_NAME_MAP.values():
                tags.append(key)

        return tags

    def get_tags(self):
        return list(self.metadata.keys())

    def edit_metadata(self, tag, new_value):
        if tag in self.FILESYSTEM_EDITABLE_FIELDS:
            return self.edit_filesystem_metadata(tag, new_value)

        if tag.startswith("XMP:"):
            xmp_tag = tag.replace("XMP:", "", 1)
            return self.edit_xmp_metadata(xmp_tag, new_value)

        return self.edit_document_metadata(tag, new_value)

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

    def edit_xmp_metadata(self, tag, new_value):
        if pikepdf is None:
            print("[!] pikepdf is not installed.")
            return False

        try:
            reverse_map = {value: key for key, value in self.XMP_NAME_MAP.items()}
            real_xmp_key = reverse_map.get(tag)

            if real_xmp_key is None:
                print(f"[!] Unknown XMP field: {tag}")
                return False

            with pikepdf.open(self.file_path, allow_overwriting_input=True) as pdf:
                with pdf.open_metadata(set_pikepdf_as_editor=False) as metadata:
                    metadata[real_xmp_key] = str(new_value)

                pdf.save(self.file_path)

            self.read_metadata()

            print(f"[+] Updated XMP field '{tag}'.")
            return True

        except Exception as error:
            print(f"[!] XMP write error: {error}")
            return False

    def edit_document_metadata(self, tag, new_value):
        if pikepdf is None:
            print("[!] pikepdf is not installed.")
            return False

        try:
            pdf_key = f"/{tag}" if not tag.startswith("/") else tag
            converted_value = self._convert_pdf_value_for_write(tag, new_value)

            with pikepdf.open(self.file_path, allow_overwriting_input=True) as pdf:
                pdf.docinfo[pdf_key] = str(converted_value)
                pdf.save(self.file_path)

            self.read_metadata()

            print(f"[+] Updated PDF metadata field '{tag}'.")
            return True

        except Exception as error:
            print(f"[!] PDF metadata write error: {error}")
            return False

    def _convert_pdf_value_for_write(self, tag, value):
        if tag in ["CreationDate", "ModDate"]:
            value = str(value).strip()

            if value.startswith("D:"):
                return value

            try:
                parsed_date = self._parse_datetime(value)
                return parsed_date.strftime("D:%Y%m%d%H%M%S")
            except ValueError:
                return value

        return str(value)

    def remove_tag(self, tag):
        if tag in self.FILESYSTEM_EDITABLE_FIELDS:
            print("[!] Filesystem timestamps cannot be removed, only modified.")
            return False

        if tag.startswith("XMP:"):
            print("[!] Direct XMP removing is not enabled in this version.")
            return False

        if pikepdf is None:
            print("[!] pikepdf is not installed.")
            return False

        try:
            pdf_key = f"/{tag}" if not tag.startswith("/") else tag

            with pikepdf.open(self.file_path, allow_overwriting_input=True) as pdf:
                if pdf_key in pdf.docinfo:
                    del pdf.docinfo[pdf_key]

                pdf.save(self.file_path)

            self.read_metadata()

            print(f"[+] Removed PDF metadata field '{tag}'.")
            return True

        except Exception as error:
            print(f"[!] PDF metadata remove error: {error}")
            return False

    def clear_all_editable_metadata(self):
        results = {}

        for tag in self.get_editable_tags():
            if tag in self.FILESYSTEM_EDITABLE_FIELDS:
                continue

            results[tag] = self.remove_tag(tag)

        return results

    def display_metadata(self):
        print("\n" + "=" * 60)
        print(f"  PDF REPORT: {os.path.basename(self.file_path)}")
        print("=" * 60)

        print("[ File Information ]")
        for key, value in self.file_info.items():
            print(f"  > {key:25}: {value}")

        print("\n[ Technical Information ]")
        for key, value in self.technical_info.items():
            print(f"  > {key:25}: {value}")

        print("\n[ Document Info Metadata ]")
        for key, value in self.document_metadata.items():
            print(f"  > {key:25}: {value}")

        print("\n[ XMP Metadata ]")
        for key, value in self.xmp_metadata.items():
            print(f"  > {key:25}: {value}")

        print("=" * 60)