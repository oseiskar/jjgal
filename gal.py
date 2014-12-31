import os, argparse, json, time, shutil, sys, glob
from PIL import ExifTags, Image as PILImage

GALLERY_DIR = '.jjgal'

def parse_arguments():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('source_dir')
    arg_parser.add_argument('--target_dir', default=None, help="default: (source_dir)")
    arg_parser.add_argument('-f', '--fresh', action='store_true')
    arg_parser.add_argument('-i', '--rewrite_index', action='store_true')
    arg_parser.add_argument('-d', '--dry_run', action='store_true')
    arg_parser.add_argument('-tw', '--thumb_width', type=int, default=200)
    arg_parser.add_argument('-th', '--thumb_height', type=int, default=150)
    arg_parser.add_argument('--title', default=None)
    arg_parser.add_argument('--frame_width', type=int, default=None)
    arg_parser.add_argument('--frame_height', type=int, default=None)
    return arg_parser.parse_args()

args = parse_arguments()

# --- helpers
class File:

    @staticmethod
    def ensure_dir_exists(filename):
        d = os.path.dirname(filename)
        if len(d) > 0 and not os.path.exists(d):
            print 'creating', d
            if not args.dry_run: os.makedirs(d)

    @staticmethod
    def write(fn, contents):
        File.ensure_dir_exists(fn)
        print 'writing', fn
        if not args.dry_run:
            with open(fn, 'w') as f:
                f.write(contents)

    @staticmethod
    def copy(src, target_dir):
        File.ensure_dir_exists(target_dir)
        print 'copying', src, 'to', target_dir
        if not args.dry_run:
            shutil.copy(src, target_dir)

    @staticmethod
    def delete(fn):
        if os.path.exists(fn):
            print 'deleting', fn
            if not args.dry_run: os.unlink(fn)

def merge_dict(a, b):
    return dict(a.items() + b.items())

class Image:
    
    THUMBNAIL_FORMAT = "jpg"
    
    thumb_name_base = str(int(time.time()))
    thumb_name_counter = 0
    
    def __init__(self, filename):
        self.img = PILImage.open(filename)
    
    @property
    def size(self): return self.img.size
    
    def process_exif(self):
        
        info = {}
        if hasattr(self.img,'_getexif') and self.img._getexif() is not None:
            
            TRANSPOSES = {
                3: PILImage.ROTATE_180,
                6: PILImage.ROTATE_270,
                8: PILImage.ROTATE_90
            }
            
            exif = {
                ExifTags.TAGS[k]: v
                for k, v in self.img._getexif().items()
                if k in ExifTags.TAGS
            }
            
            transpose = TRANSPOSES.get(exif.get('Orientation',None),None)
            if transpose is not None:
                print 'transposing by', transpose
                self.img = self.img.transpose(transpose)
            
            for k, v in exif.items():
                try:
                    MAX_LEN = 200
                    v = unicode(str(v))
                    if len(v) > MAX_LEN:
                        v = v[:MAX_LEN] + '...'
                        exif[k] = v
                except: exif[k] = '[binary]'
            
            info['exif'] = exif
            
        info['resolution'] = self.size
        
        return info
    
    def create_thumbnails(self, folder):
        
        info = {}
        info['thumb'] = self.create_thumbnail( folder, \
            args.thumb_width, args.thumb_height, quality=80)
        
        if args.frame_width is not None:
            frame_height = args.frame_height
            if frame_height == None: frame_height = args.frame_width
            info['frame'] = self.create_thumbnail( folder, \
                args.frame_width, frame_height, quality=90)
        
        return info
    
    def create_thumbnail(self, folder, max_w, max_h, **save_options):
        
        name = str(Image.thumb_name_base) + "_" + str(Image.thumb_name_counter)
        name += '.' + Image.THUMBNAIL_FORMAT
        
        Image.thumb_name_counter += 1
        
        if not args.dry_run:
            thumb = self.img.copy()
            thumb.thumbnail((max_w, max_h), PILImage.ANTIALIAS)
            thumb.save(os.path.join(folder,name), **save_options)
            
        print "\tcreated < %dx%d thumbnail %s" % (max_w, max_h, name)
        
        return name

class Gallery:
    
    META_DIR = '.jjgal'
    
    def __init__(self, src_dir, target_dir):
        """Main method"""
        
        self.root_path = src_dir
        if target_dir is None: target_dir = src_dir
        self.target_dir = target_dir
        self.data_dir = os.path.join(target_dir, Gallery.META_DIR)
        
        cached_data = {}
        
        metadata_file = os.path.join(self.data_dir, 'metadata.json')
        if args.fresh:
            glob_format = os.path.join(self.data_dir, '*.'+Image.THUMBNAIL_FORMAT)
            for f in glob.glob(glob_format):  File.delete(f)
        else:
            if os.path.exists(metadata_file):
                print 'loading', metadata_file
                with open(metadata_file) as f:
                    cached_data = json.load(f)['files']
        
        self.root_obj = Directory(self, [], cached_data)
        self.walk_and_update()
        self.write_web_files()
        self.write_metadata(metadata_file)
    
    def write_metadata(self, metadata_file):

        orig_dir = os.path.relpath(self.root_path, self.target_dir)
        if orig_dir == '.': orig_dir = ''

        File.write(metadata_file, \
            json.dumps({
                'files': self.root_obj.as_json(),
                'gallery': {
                    'original_dir': orig_dir,
                    'title': args.title
                }
            }))
    
    def write_web_files(self):
        
        src_dir = os.path.dirname(sys.argv[0])
        
        rewrite_index = args.fresh or args.rewrite_index

        if rewrite_index or not os.path.exists(os.path.join(self.data_dir,'gal.js')):
            File.copy(os.path.join(src_dir, 'gal.js'), self.data_dir)

        if rewrite_index or not os.path.exists(os.path.join(self.target_dir,'index.html')):
            File.copy(os.path.join(src_dir,'index.html'), self.target_dir)
    
    def walk_and_update(self):
        
        for root, _, files in os.walk(self.root_path):
            path = root[len(self.root_path):]
            if path == '/' or len(path) == 0: path = []
            else:
                path = path.split('/')
                if path[0] == Gallery.META_DIR:
                    print 'skipping', path
                    continue
            
            dir_obj = self.root_obj[path]
            for f in files: dir_obj.push_file(f)

class Directory:
    
    def __init__(self, gallery, rel_path=[], cached_data = {}):
        """
        gallery defines (among other things), the root directory of the
        whole structure, e.g., (e.g., '/home/user') which is the same for all
        the subdirectories. 
        
        rel_path is the path (as a list of subdirectories) from root_path to
        the subdirectory represented by this object, e.g., if
        g = Gallery('/home/user'), then Directory(g, ['Pictures', 'foobar'])
        represents the folder '/home/user/Pictures/foobar'
        
        cached_data is the stored JSON/dictionary metadata for this directory,
        if exists.
        """
        
        self.path = rel_path
        self.subdirs = {}
        self.images = {}
        self.other_files = {}
        self.gallery = gallery
        
        # in Python 2, JSON-parsed strings are unicode, OS path strings are
        # not. this causes some trouble...
        
        self.cached_data = { k : cached_data.get(k, {})
            for k in [u'subdirs', u'images', u'other_files'] }
        
    def __getitem__(self, path):
        """
        Get or create a subdirectory object. For example, if 
        g = Gallery('home/'); d = Directory(g, ['user']) then d['Pictures']
        represents the (sub)directory home/user/Pictures
        """
        
        if len(path) == 0: return self
        
        subdir = unicode(path[0])
        
        if subdir not in self.subdirs:
            self.subdirs[subdir] = Directory(self.gallery, \
                self.path + [subdir], \
                self.cached_data[u'subdirs'].get(subdir,{}))
        
        return self.subdirs[subdir][path[1:]]
    
    def as_json(self):
        """
        JSON/dictionary representation of this object
        """
        
        return {
            'subdirs': { k : v.as_json() for k,v in self.subdirs.items() },
            'images': self.images,
            'other_files': self.other_files
        }
    
    def push_file(self, f):
        """
        Should be called for each file in this directory when walking the
        directory structure (in Gallery.walk_and_update). Processes new images.
        """
        
        cached = self.cached_data[u'images'].pop(f, None)
        if cached is not None:
            self.images[f] = cached
            return
        
        cached = self.cached_data[u'other_files'].pop(f, None)
        if cached is not None:
            self.other_files[f] = cached
            return
        
        try: unicode(f)
        except:
            print "invalid encoding in", f
            return
        
        rel_path = '/'.join(self.path + [f])
        
        print 'new file', rel_path,
        
        full_path = self.gallery.root_path + rel_path
        
        (mode, ino, dev, nlink,
         uid, gid, size, atime,
         mtime, ctime) = os.stat(full_path)
        
        file_info = {
            'size': size,
            'mtime': mtime
        }
        
        try:
            img = Image(full_path)
            print '-> image of size', img.size
        
        except IOError:
            print '(not an image)'
            self.other_files[f] = file_info
            return
            
        file_info = merge_dict(file_info, img.process_exif())
        
        try:
            file_info = merge_dict(file_info, img.create_thumbnails(self.gallery.data_dir))
            self.images[f] = file_info
            
        except IOError as e:
            print 'failed to save:', e
    
    def delete_orphaned_thumbnails(self):
        """
        Remove all thumbnail images that appeared in cached_data but were not
        found when re-walking the directory structure
        """
        
        def del_and_recurse_cache(c, path):
            for s in c[u'subdirs']:
                del_and_recurse_cache(c[u'subdirs'][s], path + [s])
            for img, info in c[u'images'].items():
                File.delete(os.path.join(self.gallery.data_dir, info[u'thumb']))
                if u'frame' in info:
                    File.delete(os.path.join(self.gallery.data_dir, info[u'frame']))
        
        del_and_recurse_cache(self.cached_data, self.path)
        
Gallery(args.source_dir, args.target_dir)
