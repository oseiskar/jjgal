MainView = Backbone.View.extend({
    
    events: {
        'click .thumbnail': 'openImage',
        'click .subdir': 'openSubdir',
        'click .navigate-up': 'navigateUp',
        'click .flatten-subdirs': 'flattenSubdirs'
    },
    
    // basic boostrap initialization and rendering
    
    initialize: function(options) {
        this.web_root = '.jjgal/';
        this.current_image = null;
        this.flattened = false;
        this.fetchData();
        this.templates = {
            dir_nav:  _.template( $('#navigation-template').html() ),
            subdirs:  _.template( $('#subdirs-template').html() ),
            thumbnails:  _.template( $('#thumbnails-template').html() ),
            other_files:  _.template( $('#other-files-template').html() )
        },
        this.dir_nav = $('<div/>');
        this.main_window = $('<div/>');
        
        this.$el.append(this.dir_nav);
        this.$el.append(this.main_window);
    },
    
    fetchData: function() {
        
        var that = this;
        $.getJSON(this.web_root + 'metadata.json',
            function (data) {
                that.dataLoaded(data);
            }
        );
    },
    
    dataLoaded: function(data) {
        this.root = data.files;
        this.original_root = data.gallery.original_dir;
        this.current_path = [];
        if (data.gallery.title) document.title = data.gallery.title;
        
        this.render();
    },
    
    render: function() {
        this.dir_nav.html(this.templates.dir_nav({
            path: this.current_path
        }));
        
        if (this.current_image === null) {
            this.renderDir();
        }
        else {
            this.current_image.render();
        }
    },
    
    renderDir: function() {
        this.main_window.html('');
        
        var dir = this.getCurrentDir();
        var subdirs = this.getSortedSubdirs(dir);
        
        if (subdirs.length > 0)
            this.main_window.append(this.templates.subdirs({
                subdirs: subdirs
            }));
        
        this.main_window.append(this.templates.thumbnails({
            files: this.getSortedFiles(dir.images),
            data: dir.images,
            thumb_root: this.web_root
        }));
        
        if (_.keys(dir.other_files).length > 0) 
            this.main_window.append(this.templates.other_files({
                files: this.getSortedFiles(dir.other_files),
                data: dir.other_files,
                dir: this.getCurrentOriginalPath()
            }));
    },
    
    // button actions
    
    openImage: function(ev) {
        
        var dir = this.getCurrentDir();
        
        var image_window = $('<div>');
        this.current_image = new ImageView({
            main_view: this,
            images: dir.images,
            order: this.getSortedFiles(dir.images),
            current_index: parseInt($(ev.currentTarget).data('index')),
            path: this.getCurrentOriginalPath(),
            el: image_window
        });
        this.main_window.html('');
        this.main_window.append(image_window);
        this.render();
    },
    
    openSubdir: function(ev) {
        this.current_path.push($(ev.currentTarget).data('target'));
        this.render();
    },
    
    flattenSubdirs: function(ev) {
        this.flattened = true;
        this.render();
    },
    
    navigateUp: function(ev) {
        var lev = parseInt($(ev.currentTarget).data('level'));
        this.current_path = this.current_path.slice(0, lev+1);
        this.flattened = false;
        this.closeImage();
    },
    
    closeImage: function() {
        this.current_image = null;
        this.render();
    },
    
    // helpers
    
    getCurrentOriginalPath: function () {
        var path =  '';
        if (this.current_path.length > 0) path = this.current_path.join('/') + '/';
        if (this.original_root != '') path = this.original_root + '/' + path;
        return path;
    },
    
    getCurrentDir: function () {
        current_dir = this.root;
        for (i in this.current_path) {
            current_dir = current_dir.subdirs[this.current_path[i]];
        }
        
        if (this.flattened) {
            var flat_dir = { images: {}, other_files: {}, subdirs: {} };
            var flatten = function (dir, path) {
                for (img in dir.images)
                    flat_dir.images[path + img] = dir.images[img];
                    
                for (f in dir.other_files)
                    flat_dir.other_files[path + f] = dir.other_files[f];
                
                for (s in dir.subdirs) flatten(dir.subdirs[s], path + s + '/');
            };
            
            flatten(current_dir, '');
            return flat_dir;
        }
        else {
            return current_dir;
        }
    },
    
    getSortedFiles: function(dir) {
        
        var criterion = function (key) {
            return getImageTime(dir[key]).time;
        };
        
        var keys = _.keys(dir);
        keys.sort();
        return _.sortBy(keys, criterion);
    },
    
    getSortedSubdirs: function(dir) {
        
        var subdirs = _.keys(dir.subdirs);
        subdirs.sort(function (a,b) {
            // case-insensitive sort
            a.toLowerCase().localeCompare(b.toLowerCase());
        });
        return subdirs;
    }
});

ImageView = Backbone.View.extend({
    
    events: {
        'click .next-image': 'nextImage',
        'click .prev-image': 'prevImage',
        'click .close-image': 'closeImage'
    },
    
    initialize: function(options) {
        this.main_view = options.main_view;
        this.images = options.images;
        this.order = options.order;
        this.current_index = options.current_index;
        this.path = options.path;
        this.template =  _.template( $('#image-template').html() );
    },
    
    closeImage: function() { this.main_view.closeImage() },
    
    nextImage: function() {
        this.current_index++;
        this.render();
    },
    
    prevImage: function() {
        this.current_index--;
        this.render();
    },

    render: function(dir) {
        var img = this.order[this.current_index];
        var data = this.images[img];
        
        $('#filename-element').text(img);
        
        var original_src = this.path + img;
        var src = original_src;
        if (data.frame) src = this.main_view.web_root + data.frame;
        
        this.$el.html(this.template({
            filename: img,
            data: data,
            src: src,
            original_src: original_src,
            current_index: this.current_index,
            number_of_images: this.order.length,
            is_first: this.current_index == 0,
            is_last: this.current_index == this.order.length-1,
            image_time: getImageTime(data)
        }));
    }
});

function getImageTime(img) {
        
    if (img.exif && img.exif.DateTime) {
        // try to parse exif timestamp
        
        date_time = img.exif.DateTime.split(' ');
        iso_8601 = date_time[0].replace(/:/g,'-') + 'T' + date_time[1]
        return {
            exif: true,
            time: Date.parse(iso_8601)
        }
    }
    else {
        // mtime unix timestamp
        return {
            exif: false,
            time: parseInt(img.mtime)*1000
        }
    }
}

// Human readable file size (from StackOverflow)
function fileSize(size) {
    var i = Math.floor(Math.log(size) / Math.log(1024));
    return (size / Math.pow(1024, i)).toFixed(2) * 1 + ' '+['B', 'kB', 'MB', 'GB', 'TB'][i];
}
