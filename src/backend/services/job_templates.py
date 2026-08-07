"""Local deterministic extraction rules for the job template."""
import re


TEMPLATE_KEY = "job"
SCHEMA_VERSION = 1
EXTRACTOR = "job_label_rules"
EXTRACTOR_VERSION = "1"
FIELDS = (
    "company", "role", "location", "salary", "skills", "experience", "application_status",
)
LABELS = {
    "company": ("公司", "公司名称", "company", "employer"),
    "role": ("岗位", "职位", "岗位名称", "职位名称", "role", "position", "job title"),
    "location": ("地区", "地点", "工作地点", "location"),
    "salary": ("薪资", "薪酬", "工资", "salary", "compensation"),
    "skills": ("技能", "技能要求", "技术栈", "skills", "tech stack"),
    "experience": ("经验年限", "工作年限", "经验", "experience", "years of experience"),
    "application_status": ("投递状态", "申请状态", "进度", "application status", "status"),
}


def extract_job_fields(text: str) -> dict[str, str]:
    aliases = {
        alias.lower(): field for field, names in LABELS.items() for alias in names
    }
    result: dict[str, str] = {}
    current: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = re.match(r"^([^:：]{1,30})\s*[:：]\s*(.*)$", line)
        field = aliases.get(match.group(1).strip().lower()) if match else None
        if field:
            current = field
            value = match.group(2).strip()
            if value:
                result[field] = value[:4_000]
        elif current and current in result:
            result[current] = f"{result[current]}\n{line}"[:4_000]
    return result
