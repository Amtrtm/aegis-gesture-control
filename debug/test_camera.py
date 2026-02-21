"""
debug/test_camera.py — Quick camera connectivity test.

Usage
-----
  python test_camera.py                       # uses CAMERA_SOURCE from config
  python test_camera.py --source 0            # local webcam
  python test_camera.py --source http://phone:8080/video

Press 'q' to quit.
"""

import argparse
import sys
import os
import time

import cv2

# Allow import from parent when running standalone
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


def parse_args():
    p = argparse.ArgumentParser(description="AEGIS Camera Connection Test")
    p.add_argument("--source", type=str, default=None,
                   help="Camera source (URL, RTSP, or integer index).  Default: config.CAMERA_SOURCE")
    return p.parse_args()


def main():
    args  = parse_args()
    source = args.source if args.source is not None else config.CAMERA_SOURCE

    # Convert integer string to int
    try:
        source = int(source)
    except (ValueError, TypeError):
        pass

    print(f"\n{'='*50}")
    print(f"  AEGIS Camera Test")
    print(f"  Source: {source}")
    print(f"{'='*50}\n")

    api = cv2.CAP_DSHOW if sys.platform == "win32" and isinstance(source, int) else cv2.CAP_ANY
    cap = cv2.VideoCapture(source, api)

    if not cap.isOpened():
        print("❌  FAILED to open camera source.")
        print("\nTroubleshooting tips:")
        print("  • For RTSP:  check the IP address, port, and stream path.")
        print("  • For MJPEG: ensure the phone app (e.g. IP Webcam) is running.")
        print("  • For local: try --source 0, 1, or 2.")
        print("  • Firewall:  ensure UDP/TCP ports are open between devices.")
        print("  • VLC test:  open the URL in VLC to verify the stream works.")
        sys.exit(1)

    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    print(f"✅  Camera opened successfully!\n")

    frame_count = 0
    fps         = 0.0
    t0          = time.time()
    cv2.namedWindow("Camera Test — press Q to quit", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Camera Test — press Q to quit", 800, 600)

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            print("⚠️  Frame read failed — stream may have dropped.")
            break

        frame_count += 1
        elapsed = time.time() - t0
        if elapsed >= 1.0:
            fps     = frame_count / elapsed
            frame_count = 0
            t0 = time.time()

        h, w = frame.shape[:2]
        cv2.putText(frame,
                    f"FPS: {fps:.1f}  |  {w}x{h}  |  src: {str(source)[:40]}",
                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        cv2.imshow("Camera Test — press Q to quit", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            print("Quit requested.")
            break

    cap.release()
    cv2.destroyAllWindows()
    print("\nDone.")


if __name__ == "__main__":
    main()
