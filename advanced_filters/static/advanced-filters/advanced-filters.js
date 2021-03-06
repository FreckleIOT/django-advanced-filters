var _af_handlers = window._af_handlers || null;
var OperatorHandlers = function($) {
	var self = this;
	self.value = null;
	self.val_input = null;
	self.selected_field_elm = null;

	self.add_datepickers = function() {
		var form_id = self.val_input.parents('tr').attr('id');
		var form_num = parseInt(form_id.replace('form-', ''), 10);

		var $from = $('<input type="date">');
		$from.attr("name", "form-" + form_num + "-value_from");
		$from.attr("id", "id_form-" + form_num + "-value_from");
		$from.attr("placeholder", gettext('Start date (YYYY-MM-DD)'));
		$from.addClass('query-dt-from');
		var $to = $('<input type="date">');
		$to.attr("name", "form-" + form_num + "-value_to");
		$to.attr("id", "id_form-" + form_num + "-value_to");
		$to.attr("placeholder", gettext('End date (YYYY-MM-DD)'));
		$to.addClass('query-dt-to');

		self.val_input.parent().prepend($to);
		self.val_input.parent().prepend($from);
		var val = self.val_input.val();
		if (!val || val == 'null') {
			self.val_input.val("-");
		} else {
			from_to = val.split(',');
			if (from_to.length == 2) {
				$from.val(from_to[0])
				$to.val(from_to[1])
			}
		}
		self.val_input.css({display: 'none'});
		$from.addClass('vDateField');
		$to.addClass('vDateField');
	};

	self.remove_datepickers = function() {
		self.val_input.css({display: 'block'});
		if (self.val_input.parent().find('input.vDateField').length > 0) {
			var datefields = self.val_input.parent().find('input.vDateField');
			datefields.remove();
		}
	};

	self.modify_widget = function(elm, init) {
		// pick a widget for the value field according to operator
		self.value = $(elm).val();
		self.val_input = $(elm).parents('tr').find('.query-value');
		var row = $(elm).parents('tr');
		var value = row.find('.query-value');
		var op = row.find('.query-operator');
		if (self.value == "range") {
			self.add_datepickers();
		} else {
			self.remove_datepickers();
			if (!init){
				valueElem = $(elm).parents('tr').find('select.query-field');
				if ($(op).val() == "isnull" || $(op).val() == "istrue" || $(op).val() == "isfalse") {
					self.disable_value(value);
				} else {
					self.enable_value(value);
				}
				if ($(op).val() === 'iexact'){
					self.initialize_select2(valueElem, init)
				} else {
					self.removeSelect2(valueElem)
				}
			}
		}

	};


	self.removeSelect2 = function(elm) {
		var input = $(elm).parents('tr').find('input.query-value');
		input.select2("destroy");
		input.val('')
	}

	self.get_operators = function getOperators(elm) {
		var field = $(elm).val();
		var choicesUrl = ADVANCED_FILTER_OPERATOR_LOOKUP_URL + (FORM_MODEL ||
		MODEL_LABEL) + '/' + field;
		$.get(choicesUrl, function getChoices(data) {
		  var query = $(elm).parents('tr').find('select.query-operator');
		  var results = data.results;
		  $(query).empty()
		  for (let i = 0; i < results.length; i += 1) {
				const option = new Option(results[i].value, results[i].key);
				$(query).append($(option));
			}
			$(query).val(results[0].key).change();
		});

	};

	self.initialize_select2 = function(elm, init) {
		// initialize select2 widget and populate field choices
		let initValue = init || false;
		var field = $(elm).val();
		var choices_url = ADVANCED_FILTER_CHOICES_LOOKUP_URL + (FORM_MODEL ||
						  MODEL_LABEL) + '/' + field;
		var input = $(elm).parents('tr').find('input.query-value');
		input.select2("destroy");
		input.select2({
      minimumInputLength: ADVANCED_FILTERS_MINIMUM_INPUT,
      ajax: {
        url: choices_url,
        dataType: 'json',
        quietMillis: ADVANCED_FILTERS_QUIET_MILLIS,
        data: function data(term, page) {
          var query = {
            search: term,
            page
          };
          return query;
        },
        results: function results(data) {
          return {
            results: data.results,
            more: data.more
          };
        }
      }
		});
    if (input[0].value && initValue) {
      input.select2('data', { id: input[0].value, text: input[0].value });
    } else {
      input[0].value = null;
      input.select2('data', null);
    }
	};

	self.disable_value = function(value) {
		value.addClass("disabledbutton");
		value.children().prop('disabled',true);
		value.val(null);
		value.after('<input type="hidden" value="' + value.val() +
		'" name="' + value.attr("name") + '">');
	};

	self.disable_op = function(op) {
		op.prop("disabled", true);
		op.addClass("disabledbutton");
		op.after('<input type="hidden" value="' + op.val() +
			'" name="' + op.attr("name") + '">');
	};

	self.enable_value = function(value) {
		value.children().prop("disabled", false);
		value.removeClass("disabledbutton");
		value.siblings('input[type="hidden"]').remove();
		if (!value.val() == "null") {
			value.val("");
		}
	};

	self.enable_op = function(op) {
		op.prop("disabled", false);
		op.removeClass("disabledbutton");
		op.siblings('input[type="hidden"]').remove();
	};

	self.field_selected = function(elm, init) {
		let initValue = init || false;
		self.selected_field_elm = elm;
		var row = $(elm).parents('tr');
		var op = row.find('.query-operator');
		var value = row.find('.query-value');

		if ($(elm).val() == "_OR") {
			self.disable_value(value);
			self.disable_op(op);
		} else {
			self.get_operators(elm);
		}
		if ($(op).val() == "isnull" || $(op).val() == "istrue" || $(op).val() == "isfalse") {
			self.disable_value(value);
		}
		if ($(op).val() === 'iexact'){
			self.initialize_select2(elm, initValue)
		} else {
			self.removeSelect2(elm)
		}
	};

	self.init = function() {
		var rows = $('[data-rules-formset] tr.form-row');
		if (rows.length == 1 && rows.eq(0).hasClass('empty-form')) {
			// if only 1 form and it's empty, add first extra formset
			$('[data-rules-formset] .add-row a').click();
		}
		$('.form-row select.query-operator').each(function() {
			$(this).off("change");
			$(this).data('pre_change', $(this).val());
			$(this).on("change", function() {
				var before_change = $(this).data('pre_change');
				if ($(this).val() != before_change) self.modify_widget(this);
				$(this).data('pre_change', $(this).val());
			}).change();
			self.modify_widget(this, true);
		});
		$('.form-row select.query-field').each(function() {
			$(this).off("change");
			$(this).data('pre_change', $(this).val());
			$(this).on("change", function() {
				var before_change = $(this).data('pre_change');
				if ($(this).val() != before_change) self.field_selected(this);
				$(this).data('pre_change', $(this).val());
			}).change();
			self.field_selected($(this), true);
		});

	};

	self.destroy = function() {
		$('.form-row select.query-operator').each(function() {
			$(this).off("change");
		});
		$('.form-row select.query-field').each(function() {
			$(this).off("change");
		});
		$('.form-row input.query-value').each(function() {
			$(this).select2("destroy");
		});
	};
};

// using Grappelli's jquery if available
(function($) {
	$(document).ready(function() {
		if (!_af_handlers) {
			_af_handlers = new OperatorHandlers($);
			_af_handlers.destroy()
			_af_handlers.init();
		}
	});
})(window._jq || jQuery);
