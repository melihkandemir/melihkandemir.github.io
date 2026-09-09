module Jekyll
  module TitleCaseFilter
    # Capitalizes the first letter of every word without touching the rest,
    # so embedded acronyms (NeurIPS, GAN, ...) survive intact.
    def title_case_initials(input)
      return input if input.nil?

      input.to_s.split(/(\s+)/).map do |token|
        next token if token.strip.empty?

        token[0].upcase + token[1..-1].to_s
      end.join
    end
  end
end

Liquid::Template.register_filter(Jekyll::TitleCaseFilter)
