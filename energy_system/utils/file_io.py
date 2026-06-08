import json
from pathlib import Path


def ensure_parent_dir(path: str | Path) -> Path:
	p = Path(path)
	p.parent.mkdir(parents=True, exist_ok=True)
	return p


def append_jsonl(path: str | Path, obj: dict) -> None:
	p = ensure_parent_dir(path)
	with p.open("a", encoding="utf-8") as f:
		f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def read_jsonl(path: str | Path, max_lines: int | None = None) -> list[dict]:
	p = Path(path)
	if not p.exists():
		return []

	rows: list[dict] = []
	with p.open("r", encoding="utf-8") as f:
		for i, line in enumerate(f):
			if max_lines is not None and i >= max_lines:
				break
			line = line.strip()
			if not line:
				continue
			try:
				rows.append(json.loads(line))
			except json.JSONDecodeError:
				continue
	return rows
