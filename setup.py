from setuptools import setup

setup(
    name='wiapi',
    version='0.1.0',
    description="API server base on tornado",
    author='TM (sshwsfc)',
    author_email='sshwsfc@gmail.com',
    url='http://github.com/sshwsfc/wiapi',
    download_url='',
    license="http://www.apache.org/licenses/LICENSE-2.0",
    packages=['wiapi',],
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Framework :: Tornado',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Framework :: Tornado',
    ]
)
