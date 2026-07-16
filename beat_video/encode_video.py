"""Encode a PNG frame sequence (f_XXXX.png) to a video using Blender's bundled ffmpeg.
    blender --background --factory-startup --python encode_video.py -- <frames_dir> <out> <fps> [fmt=mp4]
      fmt = mp4  -> H.264 MP4 (RGBA frames composited over black)
            mov  -> QTRLE .mov WITH ALPHA (transparent background preserved)
"""
import bpy, os, sys

A = sys.argv[sys.argv.index("--") + 1:]
frames_dir, out_path, fps = A[0], A[1], int(A[2])
fmt = A[3] if len(A) > 3 else "mp4"
files = sorted(f for f in os.listdir(frames_dir) if f.startswith("f_") and f.endswith(".png"))
sc = bpy.context.scene
sc.sequence_editor_create()
strip = sc.sequence_editor.sequences.new_image("seq", os.path.join(frames_dir, files[0]), 1, 1)
for f in files[1:]:
    strip.elements.append(f)
strip.blend_type = 'ALPHA_OVER'
sc.frame_start = 1
sc.frame_end = len(files)
sc.render.fps = fps
img = bpy.data.images.load(os.path.join(frames_dir, files[0]))
sc.render.resolution_x, sc.render.resolution_y = img.size
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = 'FFMPEG'
if fmt == "mov":
    sc.render.film_transparent = True
    sc.render.image_settings.color_mode = 'RGBA'
    sc.render.ffmpeg.format = 'QUICKTIME'
    sc.render.ffmpeg.codec = 'QTRLE'                 # lossless RGB+alpha
else:
    sc.render.film_transparent = False
    sc.render.image_settings.color_mode = 'RGB'
    sc.render.ffmpeg.format = 'MPEG4'
    sc.render.ffmpeg.codec = 'H264'
    sc.render.ffmpeg.constant_rate_factor = 'HIGH'
    sc.render.ffmpeg.ffmpeg_preset = 'GOOD'
sc.render.filepath = out_path
bpy.ops.render.render(animation=True)
print("ENCODED", fmt, "->", out_path, len(files), "frames @", fps, "fps")
