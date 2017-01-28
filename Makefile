
POPTS:=markdown+example_lists+footnotes --number-sections

%.pdf: %.md
	pandoc -f $(POPTS) "$<" -s -o $@

