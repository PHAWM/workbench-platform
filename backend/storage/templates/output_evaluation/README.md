# Output Evaluation Template Files

This directory contains template files used when creating new user accounts with output evaluation data.

## Directory Structure

```
storage/templates/output_evaluation/
├── README.md           # This file
└── input/
    ├── metadata.csv    # Template metadata file
    └── *.wav          # Template audio files
```

## Setup Instructions

1. Create the directory structure:
   ```bash
   mkdir -p storage/templates/output_evaluation/input
   ```

2. Copy your audio files and metadata.csv:
   ```bash
   cp /path/to/your/*.wav storage/templates/output_evaluation/input/
   cp /path/to/your/metadata.csv storage/templates/output_evaluation/input/
   ```

## metadata.csv Format

The metadata.csv file should have the following columns:

```csv
id,file_name,gender,age,true_value
1,male_4_37_5e076048.wav,male,37,secure
2,male_5_35_68614d05.wav,male,35,secure
...
```

**Required columns:**
- `id`: Unique identifier for each audio file
- `file_name`: Name of the audio file (must match actual .wav file)
- `gender`: Gender label for evaluation
- `age`: Age value for evaluation
- `true_value`: Ground truth label (secure/insecure)