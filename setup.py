import setuptools

requirements, dependency_links = [], []
with open('requirements.txt') as f:
    for line in f.read().splitlines():
        if line.startswith('-e git+'):
            dependency_links.append(line.replace('-e ', ''))
        else:
            requirements.append(line)

setuptools.setup(
    name="oagdedupe",  # name of your python package
    version="2.0",
    author="Chansoo Song, Gautam Sisodia",
    license="MIT",
    url="https://github.com/chansooligans/oagdedupe",
    repository="https://github.com/chansooligans/oagdedupe",
    documentation="https://deduper.readthedocs.io/en/latest/",
    keywords=["dedupe", "entity resolution", "record linkage", "blocking"],
    packages=setuptools.find_packages(),
    install_requires=requirements,
    dependency_links=dependency_links
)
