"""Encode a PNG frame sequence (f_XXXX.png) to an H.264 MP4 using Blender's bundled ffmpeg.

    blender --background --factory-startup --python encode_video.py -- <frames_dir> <out.mp4> <fps>

Blender's FFMPEG output has no RGBA mode, so this only makes the opaque MP4
(RGBA frames composited over black). For the transparent/alpha deliverables use
ffmpeg directly — see the "Delivery encodes" section of README.md.
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
# Blender's FFMPEG output has no RGBA mode, so it can only make the opaque MP4
# (RGBA frames composited over black). The transparent video is made with ffmpeg.
sc.render.image_settings.file_format = 'FFMPEG'
sc.render.film_transparent = False
sc.render.image_settings.color_mode = 'RGB'
sc.render.ffmpeg.format = 'MPEG4'
sc.render.ffmpeg.codec = 'H264'
sc.render.ffmpeg.constant_rate_factor = 'HIGH'
sc.render.ffmpeg.ffmpeg_preset = 'GOOD'
sc.render.filepath = out_path
bpy.ops.render.render(animation=True)
print("ENCODED mp4 ->", out_path, len(files), "frames @", fps, "fps")
