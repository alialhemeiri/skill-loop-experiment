# Skill versions

Every candidate lives in its own version directory and contains a complete `SKILL.md`:

```text
03-skill/
├── README.md
└── versions/
    ├── v0/SKILL.md
    ├── v1/SKILL.md
    └── v2/SKILL.md
```

`v0` is the starting skill. To propose the next candidate, copy the current kept version into a new
directory and edit only the new copy. For example:

```bash
mkdir -p 03-skill/versions/v1
cp 03-skill/versions/v0/SKILL.md 03-skill/versions/v1/SKILL.md
```

The loop never edits a version in place. A rejected candidate remains on disk for the experiment
record, while the next candidate starts from the latest kept version.

Each `SKILL.md` must remain at or below 150 lines and 10 KB:

```bash
wc -l 03-skill/versions/v0/SKILL.md
wc -c 03-skill/versions/v0/SKILL.md
```

At G1, v0 is hash-frozen with the runner and fixtures. After that gate, changes to a frozen file
require the amendment process in `00-control/SPEC.md`.
