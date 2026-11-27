"""A small stand-in for the parts of Resolve's scripting API the builder uses."""


class Clip:
    def __init__(self, path):
        self.path = path

    def GetClipProperty(self, key):
        assert key == "File Path"
        return self.path


class Folder:
    def __init__(self, clips=(), subs=()):
        self.clips, self.subs = list(clips), list(subs)

    def GetClipList(self):
        return self.clips

    def GetSubFolderList(self):
        return self.subs


class Item:
    def __init__(self, start, duration):
        self.start, self.duration = start, duration

    def GetStart(self):
        return self.start

    def GetDuration(self):
        return self.duration


class Timeline:
    def __init__(self, name, start=86400):
        self.name, self.start, self.tracks = name, start, {1: []}

    def GetName(self):
        return self.name

    def GetStartFrame(self):
        return self.start

    def GetTrackCount(self, kind):
        return len(self.tracks)

    def AddTrack(self, kind):
        self.tracks[len(self.tracks) + 1] = []
        return True

    def GetItemListInTrack(self, kind, index):
        return self.tracks.get(index, [])


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
            t.tracks[i["trackIndex"]].append(item)
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
        assert key == "timelineFrameRate"
        return self.fps

    def SetCurrentTimeline(self, t):
        self.current = t
        return True

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
