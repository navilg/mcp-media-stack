def to_tsv(records: list[dict]) -> str:
    """Convert a list of dicts to TSV (tab-separated values) string."""
    if not records:
        return "Empty list"

    headers = list(records[0].keys())

    def _format_val(value):
        if value is None:
            return ""
        if isinstance(value, list):
            return ",".join(str(item) for item in value)
        return str(value).replace("\t", "\\t").replace("\n", "\\n")

    lines = ["\t".join(headers)]
    for record in records:
        lines.append("\t".join(_format_val(record.get(header, "")) for header in headers))

    return "\n".join(lines)
