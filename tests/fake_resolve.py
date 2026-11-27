"""A small stand-in for the parts of Resolve's scripting API the builder uses."""


class Clip:
    resolution = "1920x1080"

    def __init__(self, path):
        self.path = path

    def GetClipProperty(self, key):
        assert key in ("File Path", "Resolution")
        return self.path if key == "File Path" else self.resolution


class Folder:
    def __init__(self, clips=(), subs=()):
        self.clips, self.subs = list(clips), list(subs)

    def GetClipList(self):
        return self.clips

    def GetSubFolderList(self):
        return self.subs


class Item:
    lut_works = True

    def __init__(self, start, duration):
        self.start, self.duration, self.lut, self.props = start, duration, None, {}

    def SetProperty(self, key, value):
        assert key in ("ZoomX", "ZoomY", "Pan", "Tilt")
        self.props[key] = value
        return True

    def GetProperty(self, key):
        return self.props.get(key)

    def SetLUT(self, node, path):
        if not self.lut_works or node != 1:
            return False
        self.lut = path
        return True

    def GetStart(self):
        return self.start

    def GetDuration(self):
        return self.duration


class Timeline:
    def __init__(self, name, start=86400):
        self.name, self.start, self.tracks, self.audio = name, start, {1: []}, {1: []}
        self.markers, self.timecode = {}, "01:00:00:00"

    def GetMarkers(self):
        return dict(self.markers)

    def AddMarker(self, frame, color, name, note, duration, custom=""):
        if frame in self.markers or frame < 0:
            return False
        self.markers[frame] = {"color": color, "name": name, "note": note, "duration": duration, "customData": custom}
        return True

    def DeleteMarkerAtFrame(self, frame):
        return self.markers.pop(frame, None) is not None

    def GetCurrentTimecode(self):
        return self.timecode

    def GetName(self):
        return self.name

    def GetStartFrame(self):
        return self.start

    def _kind(self, kind):
        return self.audio if kind == "audio" else self.tracks

    def GetTrackCount(self, kind):
        return len(self._kind(kind))

    def AddTrack(self, kind):
        self._kind(kind)[len(self._kind(kind)) + 1] = []
        return True

    def GetItemListInTrack(self, kind, index):
        return self._kind(kind).get(index, [])


class MediaPool:
    def __init__(self, project, end_inclusive, missing=()):
        self.project, self.end_inclusive, self.missing = project, end_inclusive, set(missing)
        self.root = Folder()
        self.imported, self.deleted = [], []

    def GetRootFolder(self):
        return self.root

    def ImportMedia(self, paths):
        new = [Clip(p) for p in paths if p not in self.missing]
        self.root.clips += new
        self.imported += [c.path for c in new]
        return new

    def CreateEmptyTimeline(self, name):
        if any(t.name == name for t in self.project.timelines):
            return None
        t = Timeline(name)
        self.project.timelines.append(t)
        return t

    def AppendToTimeline(self, infos):
        t = self.project.current
        out = []
        for i in infos:
            length = i["endFrame"] - i["startFrame"] + (1 if self.end_inclusive else 0)
            item = Item(i["recordFrame"], length)
            (t.audio if i.get("mediaType") == 2 else t.tracks)[i["trackIndex"]].append(item)
            out.append(item)
        return out

    def DeleteTimelines(self, timelines):
        for t in timelines:
            self.project.timelines.remove(t)
            self.deleted.append(t.name)
        return True


class Project:
    def __init__(self, fps="24", end_inclusive=True, missing=()):
        self.fps, self.timelines, self.current = fps, [], None
        self.pool = MediaPool(self, end_inclusive, missing)

    def GetMediaPool(self):
        return self.pool

    def GetSetting(self, key):
        return {"timelineFrameRate": self.fps, "timelineResolutionWidth": "1080",
                "timelineResolutionHeight": "1920"}[key]

    def SetCurrentTimeline(self, t):
        self.current = t
        return True

    def GetCurrentTimeline(self):
        return self.current

    def GetTimelineCount(self):
        return len(self.timelines)

    def GetTimelineByIndex(self, i):
        return self.timelines[i - 1]


class Resolve:
    def __init__(self, project):
        self.project, self.saves = project, 0

    def GetProjectManager(self):
        return self

    def GetCurrentProject(self):
        return self.project

    def SaveProject(self):
        self.saves += 1
        return True
