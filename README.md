# DJI-LUT-Applicator
Apply DJI LUTs to videos in batches.


## Steps
1. Install FFmpeg

2. Download the LUTs from [here](https://www.dji.com/lut)

3. Run the script
```bash
python dji_lut_batch.py /path/to/videos /path/to/dji_lut.cube

# Use a different compression quality (CRF 0-51, lower is better)
python dji_lut_batch.py /path/to/videos /path/to/dji_lut.cube -c 18

# Use a different quality preset (default is medium)    
python dji_lut_batch.py /path/to/videos /path/to/dji_lut.cube -q veryfast
```


