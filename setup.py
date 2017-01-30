from distutils.core import setup

def isInt(value):
	return isinstance(value, (int,))

def formatversion(major, minor, maintenance = None):
	assert(isInt(major) and isInt(minor))
	version = [major, minor]
	if(maintenance is not None):
		assert(isInt(maintenance))
		version.append(maintenance)
	return ".".join(str(n) for n in version)

VERSION = formatversion(1,0,0)
GIT_REPO = "https://github.com/wrenoud/structobject"

setup(
  name = 'structobject',
  packages = ['structobject'], # this must be the same as the name above
  version = VERSION,
  description = 'A pythonic semantic for describing binary data structures',
  author = 'Weston Renoud',
  author_email = 'wrenoud@gmail.com',
  url = GIT_REPO, # use the URL to the github repo
  download_url = '{}/tarball/{}'.format(GIT_REPO, VERSION),
  keywords = ['struct', 'binary', 'data structures'], # arbitrary keywords
  classifiers = [],
)