function display(theCode){
	if (!theCode)theCode = $('#cf_script').text();

	var t = new Tokenizer();
	var tokens = t.tokenize_string( theCode );

	var c = new Compiler();
	var compiled = c.compile( tokens );

	var canvas = document.createElement( "canvas" );
	canvas.width = $(window).width();
	canvas.height = $(window).height();
	$(canvas).css('position', "fixed")
	  .css('top', 0)
	  .css('left', 0);
	canvas.id = "canvas";

	$("#canvas").remove();
	$("#container").before( canvas );
	
	var credit = $('#cf_credit');
	credit.css('position', 'fixed')
		.css('bottom', 5)
		.css('left', 5)
	$(canvas).after(credit)

	var r = Renderer;
	// Not clearing the queue each time will make the renderer keep rendering
	// old scripts.
	r.queue = [];
	r.render( compiled, "canvas" );
}
