import os, argparse, json, time, shutil, sys, glob
from PIL import Image, ExifTags

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

target_dir = args.target_dir
if target_dir is None: target_dir = args.source_dir
if target_dir[-1] == '/': target_dir = target_dir[:-1]

data_dir = os.path.dirname(sys.argv[0])
if len(data_dir) > 0: data_dir += '/'

target_gallery_dir = target_dir + '/.jjgal/'

def ensure_dir_exists(filename):
    d = os.path.dirname(filename)
    if len(d) > 0 and not os.path.exists(d):
        print 'creating', d
        if not args.dry_run: os.makedirs(d)

def write_file(fn, contents):
    ensure_dir_exists(fn)
    print 'writing', fn
    if not args.dry_run:
        with open(fn, 'w') as f:
            f.write(contents)

def copy_file(src, target_dir):
    ensure_dir_exists(target_dir)
    print 'copying', src, 'to', target_dir
    if not args.dry_run:
        shutil.copy(src, target_dir)

class Thumbnail:
    
    FORMAT = "jpg"
    
    name_base = str(int(time.time()))
    name_counter = 0
    
    @staticmethod
    def create(img, max_w, max_h, **save_options):
        
        name = str(Thumbnail.name_base) + "_" + str(Thumbnail.name_counter)
        name += '.' + Thumbnail.FORMAT
        
        Thumbnail.name_counter += 1
        
        if not args.dry_run:
            thumb = img.copy()
            thumb.thumbnail((max_w, max_h), Image.ANTIALIAS)
            thumb.save(target_gallery_dir + name, **save_options)
            
        print "\tcreated < %dx%d thumbnail %s" % (max_w, max_h, name)
        
        return name

class Dir:
    def __init__(self, path=[]):
        self.path = path
        self.subdirs = {}
        self.images = {}
        self.other_files = {}
        
    def __getitem__(self, path):
        
        if len(path) == 0: return self
        
        if path[0] not in self.subdirs:
            self.subdirs[path[0]] = Dir(self.path + [path[0]])
        
        return self.subdirs[path[0]][path[1:]]
    
    def as_json(self):
        return {
            'subdirs': { k : v.as_json() for k,v in self.subdirs.items() },
            'images': self.images,
            'other_files': self.other_files
        }
    
    @staticmethod
    def from_json(data, path=[]):
        d = Dir(path)
        for k,v in data['subdirs'].items():
            d.subdirs[k] = Dir.from_json(v, path + [k])
        d.images = data['images']
        d.other_files = data['other_files']
        return d
    
    def push_file(self, f, root_path):
        if f in self.other_files or f in self.images: return
        
        try: unicode(f)
        except:
            print "invalid encoding in", f
            return
        
        rel_path = '/'.join(self.path + [f])
        
        print 'new file', rel_path,
        
        full_path = root_path + rel_path
        
        (mode, ino, dev, nlink,
         uid, gid, size, atime,
         mtime, ctime) = os.stat(full_path)
        
        file_info = {
            'size': size,
            'mtime': mtime
        }
        
        try:
            img = Image.open(full_path)
            print '-> image of size', img.size
            file_info['resolution'] = img.size
            if hasattr(img,'_getexif') and img._getexif() is not None:
                file_info['exif'] = {
                    ExifTags.TAGS[k]: v
                    for k, v in img._getexif().items()
                    if k in ExifTags.TAGS
                }
            
                
            file_info['thumb'] = Thumbnail.create(img, \
                args.thumb_width, args.thumb_height, quality=80)
            
            if args.frame_width is not None:
                frame_height = args.frame_height
                if frame_height == None: frame_height = args.frame_width
                file_info['frame'] = Thumbnail.create(img, \
                    args.frame_width, frame_height, quality=90)
            
            self.images[f] = file_info
        
        except IOError:
            print '(not an image)'
            self.other_files[f] = file_info


metadata_file = target_gallery_dir + 'metadata.json'

root_obj = Dir()

if args.fresh:
    glob_format = target_gallery_dir + '*.' + Thumbnail.FORMAT
    for f in glob.glob(glob_format):
        print 'deleting', f
        if not args.dry_run: os.unlink(f)
else:
    if os.path.exists(metadata_file):
        print 'loading', metadata_file
        with open(metadata_file) as f:
            root_obj = Dir.from_json(json.load(f)['files'])

root_path = args.source_dir

for root, _, files in os.walk(root_path):
    path = root[len(root_path):]
    if path == '/' or len(path) == 0: path = []
    else:
        path = path.split('/')
        if path[0] == '.jjgal':
            print 'skipping', path
            continue
    
    dir_obj = root_obj[path]
    for f in files: dir_obj.push_file(f,root_path)

rewrite_index = args.fresh or args.rewrite_index

if rewrite_index or not os.path.exists(target_gallery_dir + 'gal.js'):
    copy_file(data_dir + 'gal.js', target_gallery_dir)

if rewrite_index or not os.path.exists(target_dir + 'index.html'):
    copy_file(data_dir + 'index.html', target_dir)

orig_dir = os.path.relpath(root_path, target_dir)
if orig_dir == '.': orig_dir = ''

write_file(metadata_file, \
    json.dumps({
        'files': root_obj.as_json(),
        'gallery': {
            'original_dir': orig_dir,
            'title': args.title
        }
    }))
